FROM python:2.7

MAINTAINER Alexander Berger <alexander.berger@jax.org>

ENV SRV_DIR=/srv/geneweaver/website-py/src \
    CONFIG_DIR=/srv/geneweaver/website-py/sample-configs/docker-configs \
    NGINX_VERSION=1.9.11-1~jessie \
    PYTHONPATH=$PYTHONPATH:/srv/geneweaver/website-py/src

COPY website-py/sample-configs/docker-configs ${CONFIG_DIR}

RUN pip install --upgrade pip \
 && pip install uwsgi \
 && wget http://geneweaver.org/sphinxapi.tar.gz && pip install sphinxapi.tar.gz \
 && pip install -r ${CONFIG_DIR}/requirements.txt 

RUN apt-key adv --keyserver hkp://pgp.mit.edu:80 --recv-keys 573BFD6B3D8FBC641079A6ABABF5BD827BD9BF62 \
 && echo "deb http://nginx.org/packages/mainline/debian/ jessie nginx" >> /etc/apt/sources.list \
 && apt-get update \
 && apt-get install -y ca-certificates \
		       nginx=${NGINX_VERSION} \
		       gettext-base \
		       mysql-client \
		       unixodbc \
		       libpq5 \
		       graphviz \
		       supervisor \
 && rm -rf /var/lib/apt/lists/* 

RUN ln -sf /dev/stdout /var/log/nginx/access.log \
 && ln -sf /dev/stderr /var/log/nginx/error.log \
 && echo "daemon off;" >> /etc/nginx/nginx.conf \
 && rm /etc/nginx/conf.d/default.conf \
 && mv ${CONFIG_DIR}/nginx.conf /etc/nginx/conf.d/ \
 && mv ${CONFIG_DIR}/gw-uwsgi.ini /srv/geneweaver \
 && mv ${CONFIG_DIR}/geneweaver.cfg /srv/geneweaver \
 && mkdir -p /etc/uwsgi/ && mv ${CONFIG_DIR}/uwsgi.ini /etc/uwsgi \
 && mv ${CONFIG_DIR}/supervisord.conf /etc/supervisord.conf

WORKDIR ${SRV_DIR}

EXPOSE 80 443 5000

#CMD ["/bin/bash"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
