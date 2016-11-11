FROM centos:7

MAINTAINER Alexander Berger <alexander.berger@jax.org>

ENV SPHINX_VERSION=2.2.9-release RE2_VERSION=2015-11-01 \
    SPHINX_INDEX_DIR=/var/idx/sphinx \
    SPHINX_LOG_DIR=/var/log/sphinx \
    SPHINX_LIB_DIR=/var/lib/sphinx \
    SPHINX_RUN_DIR=/var/run/sphinx \
    SPHINX_DIZ_DIR=/var/diz/sphinx

RUN groupadd -r rabbitmq && useradd -r -d /var/lib/rabbitmq -m -g rabbitmq rabbitmq
RUN curl -s https://packagecloud.io/install/repositories/rabbitmq/rabbitmq-server/script.rpm.sh | /bin/sh

RUN rpm -Uvh https://packages.erlang-solutions.com/erlang-solutions-1.0-1.noarch.rpm
          
RUN yum update && yum install -y \
	autoconf automake libtool gcc-c++ -y -q \
	boost \
	boost-devel \
	cairo \
	cairo-devel \
	erlang \
	git \
	graphviz \
	initscripts \
	libffi \
	libffi-devel \
	libmysqlclient.so.18 \
	libpqxx \
	libpqxx-devel \
	make \
	mysql-devel \
	postgresql-server \
	postgresql-devel \
	postgresql-libs \
	python2 \
	sphinx \
	unixODBC \
	wget tar -y -q

WORKDIR /var/lib/pgsql

RUN mkdir -p /var/lib/pgsql/restore
RUN mkdir -p /var/lib/pgsql/data

COPY DB/Restore/ode-db3-schema-2016-07-26.custom /var/lib/pgsql/restore/
COPY DB/Restore/ode-db3-data-2016-07-26.custom /var/lib/pgsql/restore/

RUN su - postgres -c "initdb -D /var/lib/pgsql/data; pg_ctl -D /var/lib/pgsql/data -l logfile start; /bin/sleep 5; createuser -s odeadmin; createdb geneweaver;"
RUN su - postgres -c "pg_restore --no-owner -Fc /var/lib/pgsql/restore/ode-db3-schema-2016-07-26.custom | psql -U postgres -d geneweaver;"
RUN su - postgres -c "pg_restore --no-owner -a -d geneweaver -Fc --disable-triggers -j6 -S postgres -U postgres /var/lib/pgsql/restore/ode-db3-data-2016-07-26.custom"