#FROM python:3.8
FROM ubuntu:22.04 as build
#COPY requirements.txt requirements.txt

ARG DEBIAN_FRONTEND=noninteractive
run apt update && apt install -y mysql-server software-properties-common
run add-apt-repository ppa:deadsnakes/ppa 

RUN apt update && apt install -y python3-pip python3.8 python3.8-venv python3.8-dev libssl-dev libcurl4-openssl-dev libpython3-dev build-essential libmysqlclient-dev autossh mysql-client pkg-config

run mkdir -p /mnt/disks/tb/tinybird_mysql_connector/syncer_files
run chmod 0755 /mnt/disks/tb/tinybird_mysql_connector/
run chmod 0755 /mnt/disks/tb/tinybird_mysql_connector/syncer_files


ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
COPY . .

run python3.8 -m pip wheel --wheel-dir=/tmp/clickkhouse-mysql-data-reader/ .
run find /tmp/clickkhouse-mysql-data-reader/ -name *.whl -exec pip install {} \;

ENTRYPOINT ["./init.sh"]
cmd ["--config-file=./clickhouse-mysql.conf"]
