#!/bin/bash

mysqld &
sleep 5
mysql -e "create user 'clickhouse_mysql_reader'@'%' identified by '1234';"
mysql -e "create database clickhouse_mysql_reader"
mysql -e "grant super on *.* to 'clickhouse_mysql_reader';"
mysql -e "grant replication slave on *.* to 'clickhouse_mysql_reader';"

mysql -e "use clickhouse_mysql_reader; create table one (id int, field varchar(10));"
mysql -e "use clickhouse_mysql_reader; create table two (id int, field varchar(10));"

clickhouse-mysql $@ #--config-file=./clickhouse-mysql.conf
