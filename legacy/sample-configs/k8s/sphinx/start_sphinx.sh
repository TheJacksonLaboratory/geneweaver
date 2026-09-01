#!/bin/bash
# Entry point for the geneweaver-legacy-search sidecar.
#
# Builds the runtime sphinx.conf (prepend the DB "source base" block, filled from the
# DB_* env, to the committed config), cold-builds the full index, then serves it with
# searchd while a background loop keeps the index fresh.

{
  echo "source base"
  echo "{"
  echo "  type = pgsql"
  echo "  sql_host = $DB_HOST"
  echo "  sql_user = $DB_USERNAME"
  echo "  sql_pass = $DB_PASSWORD"
  echo "  sql_db = $DB_NAME"
  echo "}"
  cat /app/sphinx/sphinx.conf
} > /app/sphinx/sphinx.conf.new

mv /app/sphinx/sphinx.conf.new /app/sphinx/sphinx.conf

CONF=/app/sphinx/sphinx.conf

# Cold build of the full index before serving.
indexer --all --config "$CONF"

# --- background reindexer (G3-814) --------------------------------------------
# Previously the index was built only here, at container start, so a geneset created
# after the pod came up never appeared in search until the next pod event (deploy,
# reschedule, restart). The main+delta indexes and their watermark bookkeeping are
# fully configured in sphinx.conf and already queried by search.py; this loop is the
# scheduler that was missing.
#
#   * delta every SPHINX_DELTA_INTERVAL seconds: `indexer --rotate geneset_delta`
#     rebuilds only the genesets updated since the last full build (geneset_delta_src
#     filters gs_updated >= the 'geneset' watermark), so new/edited sets appear within
#     the interval.
#   * a full `indexer --rotate --all` once a day at local midnight, which also resets
#     the watermark. The full rebuild is still required because some changes (e.g.
#     migration 118's gs_count backfill) deliberately do not bump gs_updated, so the
#     delta cannot see them.
#
# --rotate swaps the freshly built index into the running searchd via its pid_file
# (set in sphinx.conf) with no query downtime. TZ is set on the container
# (America/New_York, see the deployment), so `date` and the midnight test track ET
# across the EST/EDT transition -- a hardcoded UTC hour would not.
DELTA_INTERVAL="${SPHINX_DELTA_INTERVAL:-900}"   # 15 minutes

reindex_loop() {
    # The cold build above already produced a full index for today, so don't fire a
    # redundant full rebuild until the next local midnight.
    local last_full_day
    last_full_day="$(date +%Y-%m-%d)"
    while true; do
        sleep "$DELTA_INTERVAL"

        if ! indexer --quiet --rotate geneset_delta --config "$CONF"; then
            echo "sphinx reindexer: delta rebuild failed (will retry next interval)" >&2
        fi

        if [ "$(date +%H)" = "00" ] && [ "$(date +%Y-%m-%d)" != "$last_full_day" ]; then
            if indexer --quiet --rotate --all --config "$CONF"; then
                last_full_day="$(date +%Y-%m-%d)"
            else
                echo "sphinx reindexer: nightly full rebuild failed (will retry)" >&2
            fi
        fi
    done
}

reindex_loop &

# Serve. This is the container's foreground process, so its lifetime is the pod's.
searchd --nodetach --config "$CONF"
