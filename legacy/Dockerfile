FROM python:3.9

ENV PYTHONUNBUFFERED 1
ENV POETRY_HOME=/opt/poetry, POETRY_VIRTUALENVS_CREATE=false, POETRY_VERSION=1.8.2

RUN apt-get update && apt-get install -y \
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
    libmagickwand-dev

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

WORKDIR /app/src

CMD ["poetry", "run", "gunicorn", "--limit-request-line", "8190", "--bind", "0.0.0.0:8000", "application:app"]
