# Legacy GeneWeaver tools-worker — single image, all tools (mirrors the prod/sqa
# `geneweaver-legacy-tools` deployment). The TOOLBOX C/C++ binaries are compiled here on
# Linux (ELF), so biclique/DBSCAN/MSET behave like prod rather than a native-Mac build.
#
# Build (from the repo root), matching prod's x86-64 so the binaries are identical in kind:
#   docker build --platform linux/amd64 -f legacy/tools-worker/Dockerfile \
#     -t geneweaver-legacy-tools:local legacy
#
# Run: a single Celery worker consuming the same Redis the web app dispatches to, against
# the local Postgres, sharing the results dir with the web (see legacy/run-local.sh).
# Config is supplied at runtime via env vars (DB_*, CELERY_*, TOOLS=JSON, APPLICATION_*).

FROM python:3.9

ENV PYTHONUNBUFFERED=1 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_VERSION=1.8.2

# Build toolchain for the TOOLBOX binaries + runtime libs the tools need
# (graphviz for GeneSetViewer/PhenomeMap, imagemagick/wand, OpenMP for MSET, boost, libpq).
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential make curl \
      libboost-all-dev \
      libgomp1 \
      graphviz \
      imagemagick libmagickcore-dev libmagickwand-dev \
      libpq-dev libpqxx-dev \
      libcairo2 libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --upgrade pip && curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="${POETRY_HOME}/bin:${PATH}"

WORKDIR /app

# Python deps (reuse the legacy project's lockfile; the worker needs
# celery / numpy / pandas / psycopg2, all declared there).
COPY pyproject.toml poetry.lock README.md /app/
RUN poetry install --sync --no-root

# Worker code: the Celery app, all tool modules, and the TOOLBOX C/C++ sources.
COPY tools-worker /app/tools-worker

# Strip any prebuilt artifacts copied from the host (e.g. native-Mac binaries + stale .o
# files) so `make` recompiles from source into Linux ELF instead of skipping as up-to-date.
RUN set -eu; cd /app/tools-worker/tools/TOOLBOX; \
    find . -name '*.o' -delete; \
    for f in $(find . -type f -perm -u+x); do \
      case "$(head -c4 "$f" 2>/dev/null | od -An -tx1 | tr -d ' \n')" in \
        cffaedfe|cefaedfe|feedface|feedfacf|7f454c46) echo "removing prebuilt binary $f"; rm -f "$f";; \
      esac; \
    done

# Compile every TOOLBOX binary (biclique, dbscan, MSETcpp, bstrap, bicliquer, ...).
RUN set -eu; cd /app/tools-worker/tools/TOOLBOX; \
    for d in */ ; do \
      if [ -f "$d/Makefile" ] || [ -f "$d/makefile" ]; then \
        echo "=== building $d ==="; (cd "$d" && make clean >/dev/null 2>&1 || true; make) \
          || echo "WARN: make failed in $d"; \
      fi; \
    done

WORKDIR /app/tools-worker
CMD ["celery", "-A", "tools.celeryapp", "worker", "--loglevel=info", "--concurrency=2"]
