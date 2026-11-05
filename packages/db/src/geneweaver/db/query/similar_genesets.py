"""The gene sets most like one gene set: legacy's "Find Similar GeneSets", read-only.

Legacy (``application.dynamic_jaccard`` and ``geneweaverdb.get_similar_genesets``) found the
gene sets sharing a homology group with the viewed one through ``extsrc.hom2geneset``,
computed each one's Jaccard in Python, rewrote every ``geneset_jaccard`` row for the viewed
gene set, and read the top 500 back. This computes the same Jaccard in one read-only query,
with the run's threshold choice in place of the stored ``gsv_in_threshold`` flag, and never
writes: ``geneset_jaccard`` stays legacy's cache while legacy runs.

Membership is legacy's (``_SIMILARITY_KEY_SQL``, GWC-35 / G3-805): a gene with a homolog
counts as its homology group, so homologs across species are one gene; a gene without one
counts as itself. Jaccard is ``shared / (viewed + candidate - shared)`` over those keys.

Two differences from legacy, both deliberate:

- Candidates are gene sets sharing at least one key *under the threshold choice*. Legacy
  took every gene set in ``hom2geneset`` for the viewed set's homology groups, so it listed
  gene sets at Jaccard 0 (sharing only genes outside a threshold) and missed gene sets
  sharing only genes without a homolog. A zero is not "similar", and the missed ones are.
- The viewed gene set is not its own most similar gene set. Legacy's cache held its
  Jaccard with itself, 1.0, and the list could show it.

Checked against legacy's own ``calculate_jaccard`` on dev (2026-10-21), with the stored
``gsv_in_threshold`` flag in place of the threshold filter so both read the same genes: for
GS400340 and GS407161 the top 500 are the same gene sets in the same order with the same
Jaccard, to the last digit. Only the count compared differs, by the gene sets legacy could
not find (206 of 40,291 for GS407161).

The cost is legacy's: every gene of every candidate is read, and a gene set shares a gene
with 15,000 to 86,000 others on dev, so it takes about two minutes. That is why it runs on
AsyncTask, and why a v3 cache is planned for when legacy is turned off.
"""

from geneweaver.db.query.membership import ALL_GENES, Thresholds, membership_filter
from geneweaver.db.query.search.search import _readable
from psycopg.sql import SQL, Composed

#: Legacy listed the top 500 (``get_similar_genesets``).
DEFAULT_LIMIT = 500

#: A gene's membership key, legacy's ``_SIMILARITY_KEY_SQL``. Text, not integers:
#: ``ode_gene_id`` can be negative, so an integer surrogate could collide with a hom_id.
_KEY = SQL("CASE WHEN h.hom_id IS NULL THEN 'g' || gv.ode_gene_id ELSE 'h' || h.hom_id END")


def similar_genesets(
    geneset_id: int,
    user_id: int,
    thresholds: Thresholds = ALL_GENES,
    limit: int = DEFAULT_LIMIT,
) -> tuple[Composed, dict]:
    """The `limit` gene sets most like `geneset_id` that `user_id` may read.

    The caller must already have checked that `user_id` may read `geneset_id` itself.

    :return: The query and its parameters. Rows: ``gs_id, gs_name, gs_abbreviation, sp_id,
        cur_id, attribution, genes, shared, jaccard, viewed_genes, compared``, most similar
        first, ties by gene set id.
    """
    keep, keep_params = membership_filter(thresholds, gv="gv", gs="gs")
    readable: list = []
    params: dict = {"geneset_id": geneset_id, "limit": limit, **keep_params}
    _readable(readable, params, user_id)
    query = SQL(
        """
WITH viewed AS MATERIALIZED (
  SELECT DISTINCT {key} AS key, gv.ode_gene_id, h.hom_id
    FROM extsrc.geneset_value gv
    JOIN production.geneset gs ON gs.gs_id = gv.gs_id
    LEFT JOIN extsrc.homology h ON h.ode_gene_id = gv.ode_gene_id
   WHERE gv.gs_id = %(geneset_id)s AND {keep}
),
viewed_keys AS MATERIALIZED (SELECT DISTINCT key FROM viewed),
candidates AS MATERIALIZED (
  SELECT geneset.gs_id FROM production.geneset geneset
   WHERE geneset.gs_status NOT LIKE 'de%%'
     AND geneset.gs_id <> %(geneset_id)s
     AND {readable}
     AND geneset.gs_id IN (
       SELECT unnest(hg.geneset_array) FROM extsrc.hom2geneset hg
        WHERE hg.hom_id IN (SELECT hom_id FROM viewed WHERE hom_id IS NOT NULL)
       UNION
       SELECT gv.gs_id FROM extsrc.geneset_value gv
        WHERE gv.ode_gene_id IN (SELECT ode_gene_id FROM viewed WHERE hom_id IS NULL))
),
keys AS (
  SELECT DISTINCT gv.gs_id, {key} AS key
    FROM candidates c
    JOIN extsrc.geneset_value gv ON gv.gs_id = c.gs_id
    JOIN production.geneset gs ON gs.gs_id = gv.gs_id
    LEFT JOIN extsrc.homology h ON h.ode_gene_id = gv.ode_gene_id
   WHERE {keep}
),
scored AS (
  SELECT k.gs_id, count(*) AS genes, count(v.key) AS shared
    FROM keys k LEFT JOIN viewed_keys v ON v.key = k.key
   GROUP BY k.gs_id
),
ranked AS (
  SELECT s.gs_id, s.genes, s.shared,
         s.shared::float / ((SELECT count(*) FROM viewed_keys) + s.genes - s.shared) AS jaccard
    FROM scored s
   WHERE s.shared > 0
)
SELECT r.gs_id, g.gs_name, g.gs_abbreviation, g.sp_id, g.cur_id, a.at_abbrev AS attribution,
       r.genes, r.shared, r.jaccard,
       (SELECT count(*) FROM viewed_keys) AS viewed_genes,
       (SELECT count(*) FROM ranked) AS compared
  FROM ranked r
  JOIN production.geneset g ON g.gs_id = r.gs_id
  LEFT JOIN odestatic.attribution a ON a.at_id = g.gs_attribution
 ORDER BY r.jaccard DESC, r.gs_id
 LIMIT %(limit)s
"""
    ).format(key=_KEY, keep=keep, readable=readable[0])
    return query, params
