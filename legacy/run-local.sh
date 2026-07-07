#!/usr/bin/env bash
#
# run-local.sh - bring up the full legacy GeneWeaver stack on localhost.
#
# Services started:
#   - Postgres   (container gw-local-pg, 127.0.0.1:5433)   [must already exist]
#   - Redis      (container gw-redis,    127.0.0.1:6379)   [must already exist]  Celery broker
#   - Manticore  (container gw-manticore, 127.0.0.1:9312)  search (Sphinx API)
#   - Web        (gunicorn application:app, 127.0.0.1:8001)  the Flask UI + API
#   - Worker     (celery tools-worker)                      runs the analysis tools
#
# ONE-TIME SETUP this script does NOT do (see docs / prior setup):
#   - cd legacy && poetry install            (Python env)
#   - brew install graphviz imagemagick libomp
#   - build the TOOLBOX binaries (dbscan, biclique, MSETcpp) into tools/TOOLBOX/...
#   - create the gw-local-pg / gw-redis containers + seed the DB
#   - write legacy/src/.env and legacy/tools-worker/.env (DB/redis/results/sphinx/auth)
#   - create a login user (or configure Auth0 callback http://localhost:8001/callback)
#
# Usage:  ./legacy/run-local.sh [start|stop|status]

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LEGACY="$REPO/legacy"
SRC="$LEGACY/src"
WORKER="$LEGACY/tools-worker"
SPHINX="$LEGACY/.local/sphinx"
RESULTS="$LEGACY/.local/results"
WEB_PORT=8001
WEB_LOG=/tmp/legacy_web.log
WORKER_LOG=/tmp/legacy_worker.log
# tools-worker: single Linux image (all tools + TOOLBOX binaries), mirrors prod/sqa.
# Build once: docker build --platform linux/amd64 -f legacy/tools-worker/Dockerfile -t geneweaver-legacy-tools:local legacy
TOOLS_IMAGE=geneweaver-legacy-tools:local
TOOLS_CTR=gw-legacy-tools
# Ensure Homebrew bins (dot, etc.) are reachable by the worker + its subprocesses.
export PATH="/opt/homebrew/bin:$PATH"

say() { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!! \033[0m %s\n' "$*"; }

ensure_docker() {
  if ! docker info >/dev/null 2>&1; then
    say "Starting Docker Desktop..."
    open -a Docker || open -a "Docker Desktop" || true
    until docker info >/dev/null 2>&1; do sleep 3; done
  fi
}

start_container() {  # name
  local name="$1"
  if ! docker inspect "$name" >/dev/null 2>&1; then
    return 1  # caller decides how to create
  fi
  if [ "$(docker inspect -f '{{.State.Running}}' "$name")" != "true" ]; then
    docker start "$name" >/dev/null
  fi
}

start_manticore() {
  if start_container gw-manticore; then :; else
    say "Creating gw-manticore (building search index from the DB)..."
    mkdir -p "$SPHINX/data"; chmod 777 "$SPHINX/data"
    docker run --rm \
      -v "$SPHINX/manticore.conf":/mnt/manticore.conf:ro \
      -v "$SPHINX/data":/var/lib/manticore \
      --add-host host.docker.internal:host-gateway \
      manticoresearch/manticore:latest indexer --all --config /mnt/manticore.conf
    docker run -d --name gw-manticore \
      -p 9312:9312 -p 9306:9306 -p 9308:9308 \
      -v "$SPHINX/manticore.conf":/mnt/manticore.conf:ro \
      -v "$SPHINX/data":/var/lib/manticore \
      --add-host host.docker.internal:host-gateway \
      --entrypoint searchd \
      manticoresearch/manticore:latest --nodetach --config /mnt/manticore.conf >/dev/null
  fi
}

do_start() {
  ensure_docker

  say "Starting Postgres + Redis..."
  start_container gw-local-pg || { warn "container gw-local-pg missing - run one-time setup"; exit 1; }
  start_container gw-redis    || { warn "container gw-redis missing - run one-time setup"; exit 1; }

  say "Waiting for Postgres (127.0.0.1:5433)..."
  until PGPASSWORD=localdev psql -h 127.0.0.1 -p 5433 -U geneweaver-dev -d geneweaver-dev -tAc 'select 1' >/dev/null 2>&1; do sleep 1; done

  say "Starting Manticore search..."
  start_manticore
  until nc -z -w2 127.0.0.1 9312 2>/dev/null; do sleep 2; done

  mkdir -p "$RESULTS"

  say "Starting tools-worker container (linux/amd64, mirrors prod geneweaver-legacy-tools)..."
  pkill -f "celery -A tools.celeryapp worker" 2>/dev/null || true   # stop any native worker
  docker rm -f "$TOOLS_CTR" >/dev/null 2>&1 || true
  docker run -d --name "$TOOLS_CTR" --platform linux/amd64 \
    --add-host host.docker.internal:host-gateway \
    -e DB_HOST=host.docker.internal -e DB_PORT=5433 -e DB_NAME=geneweaver-dev \
    -e DB_USERNAME=geneweaver-dev -e DB_PASSWORD=localdev \
    -e CELERY_HOST=host.docker.internal -e CELERY_PORT=6379 \
    -e TOOLS='{"tool_dir":"/app/tools-worker/tools","results":"/results"}' \
    -e APPLICATION_RESULTS=/results \
    -v "$RESULTS":/results \
    "$TOOLS_IMAGE" >/dev/null \
    && say "  tools-worker container up ($TOOLS_CTR)" \
    || warn "  tools-worker container failed to start (build it: docker build --platform linux/amd64 -f legacy/tools-worker/Dockerfile -t $TOOLS_IMAGE legacy)"

  say "Starting web (gunicorn) on port ${WEB_PORT}"
  lsof -ti tcp:${WEB_PORT} 2>/dev/null | xargs -r kill 2>/dev/null || true
  ( cd "$SRC" && PYTHONPATH="$LEGACY" nohup poetry run gunicorn \
      --timeout 300 --limit-request-line 8190 --workers 2 \
      --bind 127.0.0.1:${WEB_PORT} application:app >"$WEB_LOG" 2>&1 & )

  until [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:${WEB_PORT}/ 2>/dev/null)" = "200" ]; do sleep 1; done
  say "Legacy GeneWeaver is up:  http://localhost:$WEB_PORT"
  echo "    logs: tail -f $WEB_LOG   |   docker logs -f $TOOLS_CTR"
  echo "    stop: $0 stop"
}

do_stop() {
  say "Stopping web..."
  lsof -ti tcp:$WEB_PORT 2>/dev/null | xargs -r kill 2>/dev/null || true
  pkill -f "celery -A tools.celeryapp worker" 2>/dev/null || true
  say "Stopping containers..."
  docker stop "$TOOLS_CTR" gw-manticore gw-redis gw-local-pg >/dev/null 2>&1 || true
  say "Stopped. (containers preserved; data intact)"
}

do_status() {
  printf '%-14s %s\n' "postgres"  "$(docker ps --filter name=gw-local-pg  --format '{{.Status}}' || echo down)"
  printf '%-14s %s\n' "redis"     "$(docker ps --filter name=gw-redis     --format '{{.Status}}' || echo down)"
  printf '%-14s %s\n' "manticore" "$(docker ps --filter name=gw-manticore --format '{{.Status}}' || echo down)"
  printf '%-14s %s\n' "tools-worker" "$(docker ps --filter name=$TOOLS_CTR --format '{{.Status}}' || echo down)"
  printf '%-14s %s\n' "web :8001" "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$WEB_PORT/ 2>/dev/null || echo down)"
}

case "${1:-start}" in
  start)  do_start ;;
  stop)   do_stop ;;
  status) do_status ;;
  *) echo "usage: $0 [start|stop|status]"; exit 2 ;;
esac
