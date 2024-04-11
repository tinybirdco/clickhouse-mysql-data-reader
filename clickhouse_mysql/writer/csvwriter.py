#!/usr/bin/env python
# -*- coding: utf-8 -*-

import csv
import os.path
import logging
import copy
import time
import uuid
import json

from clickhouse_mysql.writer.writer import Writer
from clickhouse_mysql.event.event import Event

from datetime import datetime

from pymysqlreplication.row_event import WriteRowsEvent, UpdateRowsEvent, DeleteRowsEvent


class CSVWriter(Writer):
    """Write CSV files"""

    file = None
    path = None
    writer = None
    dst_schema = None
    dst_table = None
    fieldnames = None
    header_written = False
    path_prefix = None
    path_suffix_parts = []
    delete = False

    def __init__(
            self,
            csv_file_path=None,
            csv_file_path_prefix=None,
            csv_file_path_suffix_parts=[],
            csv_keep_file=False,
            dst_schema=None,
            dst_table=None,
            dst_table_prefix=None,
            next_writer_builder=None,
            converter_builder=None,
    ):
        logging.info("CSVWriter() "
                     "csv_file_path={} "
                     "csv_file_path_prefix={} "
                     "csv_file_path_suffix_parts={} "
                     "csv_keep_file={} "
                     "dst_schema={} "
                     "dst_table={} ".format(
            csv_file_path,
            csv_file_path_prefix,
            csv_file_path_suffix_parts,
            csv_keep_file,
            dst_schema,
            dst_table,
        ))
        super().__init__(next_writer_builder=next_writer_builder, converter_builder=converter_builder)

        self.path = csv_file_path
        self.path_prefix = csv_file_path_prefix
        self.path_suffix_parts = csv_file_path_suffix_parts
        self.dst_schema = dst_schema
        self.dst_table = dst_table
        self.dst_table_prefix = dst_table_prefix

        if self.path is None:
            if not self.path_suffix_parts:
                # no suffix parts specified - use default ones
                # 1. current UNIX timestamp with fractions Ex.: 1521813908.1152523
                # 2. random-generated UUID Ex.: f42d7297-9d25-43d8-8468-a59810ce9f77
                # result would be filename like csvpool_1521813908.1152523_f42d7297-9d25-43d8-8468-a59810ce9f77.csv
                self.path_suffix_parts.append(str(time.time()))
                self.path_suffix_parts.append(str(uuid.uuid4()))
            self.path = self.path_prefix + '_'.join(self.path_suffix_parts) + '.csv'
            self.delete = not csv_keep_file

        logging.info("CSVWriter() self.path={}".format(self.path))

    def __del__(self):
        self.destroy()

    def opened(self):
        return bool(self.file)

    def open(self):
        if not self.opened():
            # do not write header to already existing file
            # assume it was written earlier
            if os.path.isfile(self.path):
                self.header_written = True
            # open file for write-at-the-end mode
            self.file = open(self.path, 'a+')


    def insert(self, event_or_events):
        # event_or_events = [
        #   event: {
        #       row: {'id': 3, 'a': 3}
        #   },
        #   event: {
        #       row: {'id': 3, 'a': 3}
        #   },
        # ]

        events = self.listify(event_or_events)
        if len(events) < 1:
            logging.warning('No events to insert. class: %s', __class__)
            return

        # assume we have at least one Event

        logging.debug('class:%s insert %d events', __class__, len(events))

        if not self.opened():
            self.open()

        if not self.writer:
            # pick any event from the list
            event = events[0]
            if not event.verify:
                logging.warning('Event verification failed. Skip insert(). Event: %s Class: %s', event.meta(), __class__)
                return

            event_converted = self.convert(event)
            rows = event_converted.pymysqlreplication_event.rows
            if 'after_values' in rows[0].keys():
                headers = list(rows[0]['after_values'].keys())
            else:
                headers = list(rows[0]['values'].keys())
            headers.insert(0, 'operation')
            headers.insert(1, 'tb_upd')
            headers.insert(2, 'table')
            headers.insert(3, 'schema')
            headers.insert(4, 'log_pos')
            headers.insert(5, 'binlog_timestamp')
            headers.insert(6, 'payload')

            # self.fieldnames = sorted(self.convert(copy.copy(event.first_row())).keys())
            self.fieldnames = headers
            if self.dst_schema is None:
                self.dst_schema = event.schema
            if self.dst_table is None:
                self.dst_table = event.table

            self.fieldnames = self.fieldnames[0:7]  # get only operation, tb_upd, table and payload

            self.writer = csv.DictWriter(self.file, fieldnames=self.fieldnames, quoting=csv.QUOTE_NONNUMERIC)
            if not self.header_written:
                self.writer.writeheader()

        for event in events:
            if not event.verify:
                logging.warning('Event verification failed. Skip one event. Event: %s Class: %s', event.meta(), __class__)
                continue # for event
            self.generate_row(event)

    def convert_null_values(self, row):
        """ We need to mark those fields that are null to be able to distinguish between NULL and empty strings """
        for key in list(row.keys()):
            if row[key] is None:
                row[key] = "NULL"

    def generate_row(self, event):
        """ When using mempool or csvpool events are cached so you can receive different kind of events in the same list. These events should be handled in a different way """
        row_w_payload = {}
        for row in event:
            row_w_payload['tb_upd'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
            if isinstance(event.pymysqlreplication_event, WriteRowsEvent):
                row_w_payload['operation'] = 0
            elif isinstance(event.pymysqlreplication_event, DeleteRowsEvent):
                row_w_payload['operation'] = 2
            else:
                row_w_payload['operation'] = 1
            row_w_payload['table'] = event.table
            row_w_payload['schema'] = str(event.schema).split('_')[0]
            row_w_payload['log_pos'] = event.pymysqlreplication_event.packet.log_pos
            row_w_payload['binlog_timestamp'] = event.pymysqlreplication_event.timestamp
            self.convert_null_values(row)
            row_w_payload['payload'] = json.dumps(row, default=str)
            self.writer.writerow(self.convert(row_w_payload))

    def push(self):
        if not self.next_writer_builder or not self.fieldnames:
            return

        event = Event()
        event.schema = self.dst_schema
        event.table = self.dst_table
        event.filename = self.path
        event.fieldnames = self.fieldnames
        self.next_writer_builder.get().insert(event)

    def close(self):
        if self.opened():
            self.file.flush()
            self.file.close()
            self.file = None
            self.writer = None

    def destroy(self):
        if self.delete and os.path.isfile(self.path):
            self.close()
            if self.next_writer_builder and self.next_writer_builder.get().not_uploaded:
                logging.error(f"CSV { self.path } not uploaded into TB")
                return
            os.remove(self.path)

if __name__ == '__main__':
    path = 'file.csv'

    writer = CSVWriter(path)
    writer.open()
    event = Event()
    event.row_converted={
        'a': 123,
        'b': 456,
        'c': 'qwe',
        'd': 'rty',
    }
    writer.insert(event)
    event.row_converted={
        'a': 789,
        'b': 987,
        'c': 'asd',
        'd': 'fgh',
    }
    writer.insert(event)
    writer.close()
