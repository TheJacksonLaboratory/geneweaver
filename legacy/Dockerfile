FROM python:3.9

ENV PYTHONUNBUFFERED 1
ENV POETRY_HOME=/opt/poetry, POETRY_VIRTUALENVS_CREATE=false, POETRY_VERSION=1.8.2

RUN DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    libboost-all-dev \
    libcairo2 \
    libcairo2-dev \
    graphviz \
    libffi-dev \
    libpqxx-dev \
    rabbitmq-server \
    sphinxsearch \
    imagemagick \
    libmagickcore-dev \
    libmagickwand-dev \
    tzdata \
    && rm -f /etc/cron.d/sphinxsearch
# tzdata: so TZ=America/New_York (set on the search sidecar) makes `date` report ET,
#   which the nightly-reindex schedule in start_sphinx.sh depends on (G3-814).
# rm /etc/cron.d/sphinxsearch: the sphinxsearch package ships an @daily reindex cron,
#   but nothing runs a cron daemon in this image, so it never fired and only misled
#   readers into thinking reindexing was scheduled. The scheduler now lives in
#   start_sphinx.sh.

# Install poetry
RUN python3 -m pip install --upgrade pip && \
    curl -sSL https://install.python-poetry.org | python3 -

ENV PATH="${POETRY_HOME}/bin:${PATH}"

WORKDIR /app

COPY sample-configs/k8s/sphinx /app/sphinx/

COPY pyproject.toml poetry.lock README.md /app/

RUN poetry install --sync --no-root

COPY /src /app/src

RUN poetry install --only-root

# Scripts run by scheduled Jobs rather than by the web container -- currently the nightly
# refresh of production.geneset_search (deploy/k8s/base/search-view-refresh-cronjob.yaml,
# G3-826). Copied after the dependency installs so editing one does not invalidate them.
#
# jobs/ rather than sample-configs/k8s/ next to start_sphinx.sh: `sample-configs/**` is
# gitignored (legacy/.gitignore), so everything under it is in the repo only by force-add and
# a later `git add -A` silently misses edits to it. A new file should not inherit that.
COPY jobs /app/jobs/

WORKDIR /app/src

CMD ["poetry", "run", "gunicorn", "--timeout", "60", "--limit-request-line", "8190", "--bind", "0.0.0.0:8000", "application:app"]
