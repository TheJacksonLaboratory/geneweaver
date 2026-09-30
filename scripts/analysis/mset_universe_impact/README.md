# MSET universe-rule impact (G3-784 / A7 decision)

Measures what changes when MSET's background moves from **genes in curated (Tier I–III)
gene sets** to **the full gene space for the species**. Results are written into the A7
decision note in `docs/v3/V3_ROADMAP_AND_GAP.md`; run these to reproduce or re-measure.

Both rules are computed against the *same* database, which is the point: comparing the new
rule to the checked-in `*BG.txt` files instead conflates the rule change with gene reloads,
and does so badly enough to invert the apparent direction for human.

## Running

Needs a database. For dev, tunnel to Cloud SQL first:

```bash
cloud-sql-proxy --port 5434 jax-compsci-nc-dev-01:us-east1:jax-dev-10-guided-jay
set -a && . ./.env.cloud-dev && set +a
export DB_PORT=5434 MSET_IMPACT_DIR=/tmp/mset-impact
mkdir -p "$MSET_IMPACT_DIR"
for s in scripts/analysis/mset_universe_impact/0*.py; do uv run python "$s"; done
```

`01` takes ~4 minutes (a grouped pass over `extsrc.geneset_value`); the rest are seconds.
All queries are read-only.

## What each step does

| script | question |
|---|---|
| `01_universe_sizes.py` | how big is each universe, per species, under both rules |
| `02_universe_membership.py` | the actual symbol sets for mouse and human, for membership tests |
| `03_sample_pairs.py` | 200 random curated same-species pairs per species, with K, n, k |
| `04_pvalue_impact.py` | p under both universes; α=0.05 verdict flips |
| `05_shift_summary.py` | how far p moves, in log10, for pairs where it moves |
| `06_refused_runs.py` | Tier IV/V sets the old background refuses outright (G3-783) |

## Why the hypergeometric

MSET is a Monte-Carlo sampling test, but its p-value is the hypergeometric tail, so `04`
and `05` compute that directly and can sweep hundreds of pairs. Validated against the real
`MSETcpp` binary at N=20,000, K=200, n=300: agreement within 0.6% across p = 0.01–0.58
(k=3..8). Beyond that the binary hits its Monte-Carlo floor (1/trials) while the analytic
form keeps resolving, which is the other reason to prefer it here.
