FROM python:3.7-slim

LABEL org.jax.project="Geneweaver"

LABEL org.opencontainers.image.authors="alexander.berger@jax.org"
LABEL org.opencontainers.image.source="https://github.com/bergsalex/geneweaver-ortholog-normalizer.git"
LABEL org.opencontainers.image.version="0.0.4"

# The default port for gunicorn
ENV PORT 8000
EXPOSE $PORT
ENV APP_HOME /opt/geneweaver_ortholog_normalizer
ENV STATIC_ROOT /srv/geneweaver_ortholog_normalizer/static/
ENV PYTHONUNBUFFERED 1

# Setup python and working directory
RUN mkdir -p $APP_HOME $VENV_DIR $STATIC_ROOT

# Grab source code and install requirements
COPY . $APP_HOME
WORKDIR $APP_HOME
RUN pip install --upgrade pip && pip install -r requirements.txt

# The entrypoint script is always run on container creation
ENTRYPOINT ["deploy/entrypoint.sh"]

# The default container command
CMD gunicorn --workers=2 --threads=4 -b :$PORT src.application:app