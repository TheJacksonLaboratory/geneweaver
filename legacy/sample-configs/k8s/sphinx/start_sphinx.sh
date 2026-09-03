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

# --- per-replica watermark keys (G3-814) --------------------------------------------
# sphinx.conf tracks the full-build watermark in production.sphinxcounters, keyed by
# index_name: 'geneset_tmp' is stamped when a full build starts and promoted to
# 'geneset' when it succeeds; the delta source then selects gs_updated >= 'geneset'.
# The index files themselves are container-local (path = /app/sphinx/..., on the
# overlay fs), so every replica has to build its own -- but those two watermark rows
# are shared, and the prod overlay runs replicas: 4. Four sidecars on one schedule
# would DELETE/INSERT the same rows concurrently:
#
#   * two interleaved pre steps (DELETE, DELETE, INSERT, INSERT) leave TWO
#     'geneset_tmp' rows. Every watermark read is a scalar subquery, so the next one
#     fails with "more than one row returned by a subquery used as an expression" and
#     the full build dies.
#   * two interleaved post steps can leave NONE (the second DELETE removes the row the
#     first just promoted, and its own UPDATE then matches nothing). The delta's
#     watermark read returns NULL, `gs_updated >= NULL` is NULL, and the delta
#     silently indexes zero rows -- stale search results with no error anywhere.
#
# Per-replica keys make the watermark mean what it has to mean here: the start of
# *this* container's last full build. Keyed on a short hash of the pod name so the key
# stays narrow regardless of pod-name length; override with SPHINX_INDEX_KEY.
#
# One row pair per distinct pod name accumulates in sphinxcounters (a few per
# rollout, self-replaced on restart for the 'geneset_tmp' half). Harmless and tiny;
# deliberately not auto-pruned, because pruning on age would delete the live
# watermark of any replica whose nightly full build had been failing, which converts
# a loud failure into a silent one.
IDX_KEY="${SPHINX_INDEX_KEY:-$(hostname | md5sum | cut -c1-8)}"
sed -i \
    -e "s/index_name='geneset_tmp'/index_name='geneset_tmp:${IDX_KEY}'/g" \
    -e "s/index_name='geneset'/index_name='geneset:${IDX_KEY}'/g" \
    -e "s/VALUES ('geneset_tmp', NOW())/VALUES ('geneset_tmp:${IDX_KEY}', NOW())/g" \
    "$CONF"

# Cold build of the full index before serving. Fatal on failure: searchd would
# otherwise come up and serve an absent or half-written index, which looks healthy to
# Kubernetes while every query returns nothing. Dying here lets the kubelet restart
# the container instead. Retry behaviour stays limited to the background refreshes
# below, which always have a good index to fall back on.
if ! indexer --all --config "$CONF"; then
    echo "sphinx: cold index build failed; refusing to serve an absent/partial index" >&2
    exit 1
fi

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
#     the interval. This depends on the write paths actually bumping gs_updated:
#     geneweaverdb.update_geneset sets it in the same UPDATE as the edit. (It used to
#     be bumped only by update_geneset_date() when the edit page was *opened*, so a
#     page held open across a nightly full build produced a save the delta could never
#     see -- stale until the next full rebuild.)
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
