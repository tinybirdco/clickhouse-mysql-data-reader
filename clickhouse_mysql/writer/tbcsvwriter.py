#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import tempfile

from clickhouse_mysql.writer.writer import Writer
from clickhouse_mysql.tableprocessor import TableProcessor

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import shutil

class TBCSVWriter(Writer):
    """Write into Tinybird via CSV file"""

    dst_schema = None
    dst_table = None
    dst_distribute = None

    tb_host = None
    tb_token = None

    def __init__(
            self,
            tb_host,
            tb_token,
            dst_schema=None,
            dst_table=None,
            dst_table_prefix=None,
            dst_distribute=False,
    ):
        # if dst_distribute and dst_schema is not None:
        #     dst_schema += "_all"
        # if dst_distribute and dst_table is not None:
        #     dst_table += "_all"
        # logging.info(
        #     "CHCSWriter() connection_settings={} dst_schema={} dst_table={}".format(connection_settings, dst_schema,
        #                                                                             dst_table))
        self.tb_host = tb_host
        self.tb_token = tb_token

        if self.tb_host is None or self.tb_token is None:
            logging.critical(f" Host: {self.tb_host} or token {self.tb_token} is missing")
            return None

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

        logging.debug('class:%s insert %d rows', __class__, len(events))

        for event in events:
            #schema = self.dst_schema if self.dst_schema else event.schema
            table = self.dst_table if self.dst_table else event.table
            params = {
                'name': table,
                'mode': 'append'
            }

            with open(event.filename, 'rb') as csv_file:
                m = MultipartEncoder(fields={'csv': ('csv', csv_file, 'text/csv')})
                url = f"{self.tb_host}/v0/datasources"
                response = requests.post(url, data=m,
                    headers={'Authorization': 'Bearer ' + self.tb_token, 'Content-Type': m.content_type},
                    params=params
                )
            
                json_response = response.json()
                invalid_lines = json_response['invalid_lines']
                quarantine_rows = json_response['quarantine_rows']
                if response.status_code == 200 and invalid_lines == 0 and quarantine_rows == 0:
                    logging.debug(f"Import response {json_response}")
                    return 

                logging.error(f"Import response {json_response}")
                with tempfile.NamedTemporaryFile(mode='wb', delete=False) as tmp_file:
                    shutil.copyfile(event.filename, f"/tmp/{tmp_file.name}")
                    
                logging.error("Dumped in %s", tmp_file.name)

        pass

    def deleteRow(self, event_or_events=None):
        # event_or_events = [
        #   event: {
        #       row: {'id': 3, 'a': 3}
        #   },
        #   event: {
        #       row: {'id': 3, 'a': 3}
        #   },
        # ]

        # events = self.listify(event_or_events)
        # if len(events) < 1:
        #     logging.warning('No events to delete. class: %s', __class__)
        #     return

        # # assume we have at least one Event

        # logging.debug('class:%s delete %d rows', __class__, len(events))

        # for event in events:
        #     schema = self.dst_schema if self.dst_schema else event.schema
        #     table = None
        #     if self.dst_distribute:
        #         table = TableProcessor.create_distributed_table_name(db=event.schema, table=event.table)
        #     else:
        #         table = self.dst_table if self.dst_table else event.table
        #         if self.dst_schema:
        #             table = TableProcessor.create_migrated_table_name(prefix=self.dst_table_prefix, table=table)

        #     sql = 'ALTER TABLE `{0}`.`{1}` DELETE WHERE {2} = {3} '.format(
        #         schema,
        #         table,
        #         ' AND '.join(map(lambda column: '`%s`' % column, event.fieldnames)),
        #     )

        #     choptions = ""
        #     if self.host:
        #         choptions += " --host=" + shlex.quote(self.host)
        #     if self.port:
        #         choptions += " --port=" + str(self.port)
        #     if self.user:
        #         choptions += " --user=" + shlex.quote(self.user)
        #     if self.password:
        #         choptions += " --password=" + shlex.quote(self.password)
        #     bash = "tail -n +2 '{0}' | clickhouse-client {1} --query='{2}'".format(
        #         event.filename,
        #         choptions,
        #         sql,
        #     )

        #     logging.info('starting clickhouse-client process for delete operation')
        #     logging.debug('starting %s', bash)
        #     os.system(bash)
        
        logging.debug("CHCSVWriter: delete row")
        pass

    def update(self, event_or_events=None):
        # event_or_events = [
        #   event: {
        #       row: {'id': 3, 'a': 3}
        #   },
        #   event: {
        #       row: {'id': 3, 'a': 3}
        #   },
        # ]

        # logging.info('starting clickhouse-client process for update operation')

        # events = self.listify(event_or_events)
        # if len(events) < 1:
        #     logging.warning('No events to update. class: %s', __class__)
        #     return

        # # assume we have at least one Event

        # logging.debug('class:%s update %d rows', __class__, len(events))

        # for event in events:
        #     schema = self.dst_schema if self.dst_schema else event.schema
        #     table = None
        #     if self.dst_distribute:
        #         table = TableProcessor.create_distributed_table_name(db=event.schema, table=event.table)
        #     else:
        #         table = self.dst_table if self.dst_table else event.table
        #         if self.dst_schema:
        #             table = TableProcessor.create_migrated_table_name(prefix=self.dst_table_prefix, table=table)

        #     sql = 'INSERT INTO `{0}`.`{1}` ({2}) FORMAT CSV'.format(
        #         schema,
        #         table,
        #         ', '.join(map(lambda column: '`%s`' % column, event.fieldnames)),
        #     )

        #     sql = 'ALTER TABLE `{0}`.`{1}` UPDATE {3}'.format(
        #         schema,
        #         table,
        #         ', '.join(map(lambda column, value: '`%s`=`%s' % column, event.fieldnames, event.fieldnames))
        #     )

        #     choptions = ""
        #     if self.host:
        #         choptions += " --host=" + shlex.quote(self.host)
        #     if self.port:
        #         choptions += " --port=" + str(self.port)
        #     if self.user:
        #         choptions += " --user=" + shlex.quote(self.user)
        #     if self.password:
        #         choptions += " --password=" + shlex.quote(self.password)
        #     bash = "tail -n +2 '{0}' | clickhouse-client {1} --query='{2}'".format(
        #         event.filename,
        #         choptions,
        #         sql,
        #     )

        #     logging.info('starting clickhouse-client process')
        #     logging.debug('starting %s', bash)
        #     os.system(bash)

        logging.debug("CHCSVWriter: delete row")

        pass