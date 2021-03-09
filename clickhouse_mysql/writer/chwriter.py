#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import sys

from decimal import Decimal

from clickhouse_mysql.dbclient.chclient import CHClient

from clickhouse_mysql.writer.writer import Writer
from clickhouse_mysql.tableprocessor import TableProcessor
from clickhouse_mysql.event.event import Event


class CHWriter(Writer):
    """ClickHouse writer"""

    client = None
    dst_schema = None
    dst_table = None
    dst_distribute = None

    def __init__(
            self,
            connection_settings,
            dst_schema=None,
            dst_table=None,
            dst_table_prefix=None,
            dst_distribute=False,
            next_writer_builder=None,
            converter_builder=None,
    ):
        if dst_distribute and dst_schema is not None:
            dst_schema += "_all"
        if dst_distribute and dst_table is not None:
            dst_table += "_all"
        logging.info("CHWriter() connection_settings={} dst_schema={} dst_table={} dst_distribute={}".format(
            connection_settings, dst_schema, dst_table, dst_distribute))
        self.client = CHClient(connection_settings)
        self.dst_schema = dst_schema
        self.dst_table = dst_table
        self.dst_table_prefix = dst_table_prefix
        self.dst_distribute = dst_distribute

    def insert(self, event_or_events=None):
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

        logging.debug('class:%s insert %d event(s)', __class__, len(events))

        # verify and converts events and consolidate converted rows from all events into one batch

        rows = []
        event_converted = None
        for event in events:
            if not event.verify:
                logging.warning('Event verification failed. Skip one event. Event: %s Class: %s', event.meta(), __class__)
                continue # for event

            event_converted = self.convert(event)
            for row in event_converted:
                for key in row.keys():
                    # we need to convert Decimal value to str value for suitable for table structure
                    if type(row[key]) == Decimal:
                        row[key] = str(row[key])
                rows.append(row)

        logging.debug('class:%s insert %d row(s)', __class__, len(rows))

        # determine target schema.table

        schema = self.dst_schema if self.dst_schema else event_converted.schema
        table = None
        if self.dst_distribute:
            table = TableProcessor.create_distributed_table_name(db=event_converted.schema, table=event_converted.table)
        else:
            table = self.dst_table if self.dst_table else event_converted.table
            if self.dst_schema:
                table = TableProcessor.create_migrated_table_name(prefix=self.dst_table_prefix, table=table)

        logging.debug("schema={} table={} self.dst_schema={} self.dst_table={}".format(schema, table, self.dst_schema, self.dst_table))

        # and INSERT converted rows

        sql = ''
        try:
            sql = 'INSERT INTO `{0}`.`{1}` ({2}) VALUES'.format(
                schema,
                table,
                ', '.join(map(lambda column: '`%s`' % column, rows[0].keys()))
            )
            self.client.execute(sql, rows)
        except Exception as ex:
            logging.critical('QUERY FAILED')
            logging.critical('ex={}'.format(ex))
            logging.critical('sql={}'.format(sql))
            sys.exit(0)

        # all DONE

    def deleteRow(self, event_or_events):
        # event_or_events = [
        #   event: {
        #       row: {'id': 3, 'a': 3}
        #   },
        #   event: {
        #       row: {'id': 3, 'a': 3}
        #   },
        # ]

        logging.debug("Delete CHWriter")

        events = self.listify(event_or_events)
        if len(events) < 1:
            logging.warning('No events to insert. class: %s', __class__)
            return

        # assume we have at least one Event

        logging.debug('class:%s delete %d event(s)', __class__, len(events))

        # verify and converts events and consolidate converted rows from all events into one batch

        rows = []
        event_converted = None
        for event in events:
            if not event.verify:
                logging.warning('Event verification failed. Skip one event. Event: %s Class: %s', event.meta(),
                                __class__)
                continue  # for event

            event_converted = self.convert(event)
            for row in event_converted:
                for key in row.keys():
                    # we need to convert Decimal value to str value for suitable for table structure
                    if type(row[key]) == Decimal:
                        row[key] = str(row[key])
                rows.append(row)

        logging.debug('class:%s delete %d row(s)', __class__, len(rows))

        # determine target schema.table

        schema = self.dst_schema if self.dst_schema else event_converted.schema
        table = None
        if self.dst_distribute:
            table = TableProcessor.create_distributed_table_name(db=event_converted.schema, table=event_converted.table)
        else:
            table = self.dst_table if self.dst_table else event_converted.table
            if self.dst_schema:
                table = TableProcessor.create_migrated_table_name(prefix=self.dst_table_prefix, table=table)

        logging.debug("schema={} table={} self.dst_schema={} self.dst_table={}".format(schema, table, self.dst_schema,
                                                                                       self.dst_table))

        # and DELETE converted rows

        sql = ''
        try:
            sql = 'ALTER TABLE `{0}`.`{1}` DELETE WHERE {2} = {3} '.format(
                schema,
                table,
                ' AND '.join(map(lambda column: '`%s`' % column, event.fieldnames)),
            )
            self.client.execute(sql, rows)
        except Exception as ex:
            logging.critical('QUERY FAILED')
            logging.critical('ex={}'.format(ex))
            logging.critical('sql={}'.format(sql))
            sys.exit(0)

        # all DONE

    """
        Get string format pattern for update and delete operations
    """
    def get_data_format(self, column, value):
        t = type(value)
        if t == str:
            return "`%s`='%s'" % (column, value)
        else:
            # int, float
            return "`%s`=%s" % (column, value)

    def update(self, event_or_events):
        # event_or_events = [
        #   event: {
        #       row: {'id': 3, 'a': 3}
        #   },
        #   event: {
        #       row: {'id': 3, 'a': 3}
        #   },
        # ]

        logging.debug("Update CHWriter")

        events = self.listify(event_or_events)
        if len(events) < 1:
            logging.warning('No events to update. class: %s', __class__)
            return

        # assume we have at least one Event

        logging.debug('class:%s update %d event(s)', __class__, len(events))

        # verify and converts events and consolidate converted rows from all events into one batch

        rows = []
        event_converted = None
        pk = None
        for event in events:
            if not event.verify:
                logging.warning('Event verification failed. Skip one event. Event: %s Class: %s', event.meta(),
                                __class__)
                continue  # for event

            event_converted = self.convert(event)
            pk = event_converted.pymysqlreplication_event.primary_key
            for row in event_converted.pymysqlreplication_event.rows:
                for key in row['after_values'].keys():
                    # we need to convert Decimal value to str value for suitable for table structure
                    if type(row['after_values'][key]) == Decimal:
                        row['after_values'][key] = str(row['after_values'][key])
                rows.append(row)

        logging.debug('class:%s update %d row(s)', __class__, len(rows))

        # determine target schema.table

        schema = self.dst_schema if self.dst_schema else event_converted.schema
        table = None
        if self.dst_distribute:
            table = TableProcessor.create_distributed_table_name(db=event_converted.schema, table=event_converted.table)
        else:
            table = self.dst_table if self.dst_table else event_converted.table
            if self.dst_schema:
                table = TableProcessor.create_migrated_table_name(prefix=self.dst_table_prefix, table=table)

        logging.debug("schema={} table={} self.dst_schema={} self.dst_table={}".format(schema, table, self.dst_schema,
                                                                                       self.dst_table))

        # and UPDATE converted rows

        sql = ''
        try:
            sql = 'ALTER TABLE `{0}`.`{1}` UPDATE {2} where {3}'.format(
                schema,
                table,
                ', '.join(filter(None, map(lambda column, value: "" if column == pk else self.get_data_format(column, value), row['after_values'].keys(), row['after_values'].values()))),
                ' and '.join(map(lambda column, value: self.get_data_format(column, value), row['before_values'].keys(), row['before_values'].values()))
            )

            # sql = "ALTER TABLE `test`.`animals` UPDATE `name`='pajaroTO', `position`=1 where `id`=1 and `name`='oso'"
            self.client.execute(sql)
        except Exception as ex:
            logging.critical('QUERY FAILED')
            logging.critical('ex={}'.format(ex))
            logging.critical('sql={}'.format(sql))
            # sys.exit(0)

        # all DONE




if __name__ == '__main__':
    connection_settings = {
        'host': '192.168.74.230',
        'port': 9000,
        'user': 'default',
        'passwd': '',
    }

    writer = CHWriter(connection_settings=connection_settings)
    writer.insert()
