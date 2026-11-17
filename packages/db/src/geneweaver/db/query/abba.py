"""Query builders for the ABBA tool (gene/gene-set association lookup).

Ports the legacy ``ABBA`` Celery task (``legacy/tools-worker/tools/ABBA.py``) into
versioned, parameterised db-layer queries. ABBA takes a set of input genes (text-supplied
and/or pulled from input gene sets), expands them by homology, finds the gene sets that
contain those "genes of interest", and reports the genes that recur across those gene sets.

This is a multi-step SQL pipeline (it builds four session temp tables), so the heavy work
stays in Postgres -- it does not fit the in-memory ``AbstractTool`` framework. The SQL now
lives in code: testable and reviewable.

Improvements over the legacy SQL:

  - **No string-interpolated values.** The legacy built ``IN (...)`` clauses by joining
    Python lists into the SQL text (an injection risk and a quoting hazard). Here list
    values bind as parameters via ``= ANY(%(...)s)``, and temp-table names are
    ``sql.Identifier`` (safely quoted).
  - **No-homology branch fixed.** The legacy "ignore homology" path ran a bare
    ``SELECT * FROM input`` and never created the genes-of-interest table, breaking every
    later step; here it creates the table as a copy of the input genes.

Schema qualifications match the legacy tool (``extsrc``/``production``/``odestatic``).
``gdb_id = 7`` is the Gene Symbol identifier source, as in the legacy tool.
"""

from geneweaver.db.query.membership import ALL_GENES, Thresholds, membership_filter
from geneweaver.db.query.readable import readable_by
from psycopg.sql import SQL, Composed, Identifier

# Gene-identifier source used throughout ABBA (Gene Symbol), as in the legacy tool.
GENE_SYMBOL_GDB_ID = 7

# Every step that reads gene-set membership takes the run's ``thresholds``
# (`geneweaver.db.query.membership`): every gene by default, the uploader's stored cutoff,
# or the run's own per score type. Legacy only ever used the stored in-threshold flag.


def _table(name: str) -> Identifier:
    """Wrap a (caller-generated) temp-table name as a safely-quoted identifier."""
    return Identifier(name)


def ref_ids_for_genesets(
    geneset_ids: list[int], thresholds: Thresholds = ALL_GENES
) -> tuple[Composed, dict]:
    """The preferred gene symbol of each gene in the given gene sets, without repeats.

    One per gene. Legacy took every identifier of every gene (Entrez, Ensembl, RefSeq, every
    symbol synonym): the seed only matches gene symbols, so the rest matched nothing, but a
    synonym matched every *other* gene sharing it, pulling unrelated genes into the seed,
    and the list grew several times larger than the gene sets.
    """
    member, params = membership_filter(thresholds, gv="gsv", gs="gs")
    query = SQL(
        """
        SELECT DISTINCT ode_ref_id
          FROM extsrc.gene g, extsrc.geneset_value gsv, production.geneset gs
         WHERE gsv.gs_id = ANY(%(gs_ids)s)
           AND gs.gs_id = gsv.gs_id
           AND {member}
           AND gsv.ode_gene_id = g.ode_gene_id
           AND g.gdb_id = %(gdb_id)s
           AND g.ode_pref
        """
    ).format(member=member)
    return query, {"gs_ids": geneset_ids, "gdb_id": GENE_SYMBOL_GDB_ID, **params}


def create_input_genes_table(
    table: str, input_genes: list[str], species_ids: list[int]
) -> tuple[Composed, dict]:
    """Create the input-genes temp table from lower-cased reference ids (symbols).

    ``input_genes`` must already be lower-cased by the caller (matched against
    ``lower(ode_ref_id)``).
    """
    query = SQL(
        """
        CREATE TEMP TABLE {table} ON COMMIT DROP AS
        SELECT * FROM extsrc.gene
         WHERE lower(ode_ref_id) = ANY(%(genes)s)
           AND sp_id = ANY(%(species)s)
           AND gdb_id = %(gdb_id)s
        """
    ).format(table=_table(table))
    return query, {
        "genes": [g.lower() for g in input_genes],
        "species": species_ids,
        "gdb_id": GENE_SYMBOL_GDB_ID,
    }


def create_genes_of_interest_table(
    interest_table: str,
    input_table: str,
    species_ids: list[int],
    *,
    include_homology: bool,
) -> tuple[Composed, dict]:
    """Create the genes-of-interest temp table (input genes, plus homologs if requested)."""
    if not include_homology:
        # Legacy bug fixed: copy the input genes into the interest table (the legacy
        # path ran a bare SELECT and never created this table).
        query = SQL("CREATE TEMP TABLE {interest} ON COMMIT DROP AS SELECT * FROM {input}").format(
            interest=_table(interest_table), input=_table(input_table)
        )
        return query, {}
    query = SQL(
        """
        CREATE TEMP TABLE {interest} ON COMMIT DROP AS
        (SELECT * FROM extsrc.gene
          WHERE ode_gene_id IN
            (SELECT ode_gene_id FROM extsrc.homology WHERE hom_id IN
              (SELECT hom_id FROM extsrc.homology h
                 JOIN {input} ig ON h.ode_gene_id = ig.ode_gene_id))
            AND gdb_id = %(gdb_id)s
            AND ode_pref = true
            AND sp_id = ANY(%(species)s))
        UNION DISTINCT (SELECT * FROM {input})
        """
    ).format(interest=_table(interest_table), input=_table(input_table))
    return query, {"gdb_id": GENE_SYMBOL_GDB_ID, "species": species_ids}


def create_matching_genesets_table(
    matching_table: str,
    interest_table: str,
    user_id: int,
    thresholds: Thresholds = ALL_GENES,
) -> tuple[Composed, dict]:
    """Create the matching-gene-sets temp table: gene sets containing genes of interest.

    ``geneMatchCount`` is the number of genes-of-interest each gene set contains. Only gene
    sets the user may read match (`geneweaver.db.query.readable`), the rule search and a tool
    run use. Legacy's own rule -- every group of the gene set must be one of the user's --
    hid the user's own private gene sets and an admin's or curator's view, and admitted a
    gene set with no groups to anyone.
    """
    member, params = membership_filter(thresholds, gv="gv", gs="gs")
    query = SQL(
        """
        CREATE TEMP TABLE {matching} ON COMMIT DROP AS
        SELECT count(ode_gene_id) AS genematchcount, gs.*
          FROM extsrc.geneset_value gv
          JOIN production.geneset gs ON gv.gs_id = gs.gs_id
         WHERE ode_gene_id IN (SELECT ode_gene_id FROM {interest})
           AND gs_status = 'normal'
           AND {member}
           AND {readable}
         GROUP BY gs.gs_id
        """
    ).format(
        matching=_table(matching_table),
        interest=_table(interest_table),
        member=member,
        readable=readable_by("gs", "user_id"),
    )
    return query, {"user_id": user_id, **params}


def create_result_genes_table(
    result_table: str,
    matching_table: str,
    interest_table: str,
    tiers: list[int],
    species_ids: list[int],
    min_genes: int | None,
    thresholds: Thresholds = ALL_GENES,
) -> tuple[Composed, dict]:
    """Create the result-genes temp table: genes recurring across the matching gene sets.

    ``min_genes`` gates the matching gene sets by ``geneMatchCount``. When it is ``None``
    (the legacy "auto" default), the gate is ``least(count(distinct genes of interest), 1)``.
    Genes already in the input (genes of interest) are excluded from the results.
    """
    member, member_params = membership_filter(thresholds, gv="gv", gs="gs")
    if min_genes is None:
        min_genes_expr: Composed = SQL(
            "least((SELECT count(DISTINCT ode_ref_id) FROM {interest}), 1)"
        ).format(interest=_table(interest_table))
        params: dict = {}
    else:
        min_genes_expr = SQL("%(min_genes)s")
        params = {"min_genes": min_genes}
    query = SQL(
        """
        CREATE TEMP TABLE {result} ON COMMIT DROP AS
        SELECT gi.*, count(gv.ode_gene_id) AS occurrences
          FROM extsrc.geneset_value gv
          JOIN extsrc.gene_info gi ON gv.ode_gene_id = gi.ode_gene_id
          JOIN production.geneset gs ON gs.gs_id = gv.gs_id
         WHERE {member}
           AND gv.gs_id IN
             (SELECT gs_id FROM {matching}
               WHERE genematchcount >= {min_genes}
                 AND cur_id = ANY(%(tiers)s)
                 AND sp_id = ANY(%(species)s))
         GROUP BY gi.ode_gene_id
        HAVING lower(gi.gi_symbol) NOT IN
             (SELECT DISTINCT lower(ode_ref_id) FROM {interest})
        """
    ).format(
        result=_table(result_table),
        matching=_table(matching_table),
        interest=_table(interest_table),
        min_genes=min_genes_expr,
        member=member,
    )
    params.update({"tiers": tiers, "species": species_ids, **member_params})
    return query, params


def drop_table(table: str) -> tuple[Composed, dict]:
    """Drop a temp table if it exists (idempotent setup)."""
    return SQL("DROP TABLE IF EXISTS {table}").format(table=_table(table)), {}


# --------------------------------------------------------------------- result/metadata


def count_available_genes() -> tuple[Composed, dict]:
    """Total number of preferred gene symbols available."""
    return (
        SQL(
            "SELECT count(*) FROM extsrc.gene WHERE gdb_id = %(gdb_id)s AND ode_pref = TRUE"
        ).format(),
        {"gdb_id": GENE_SYMBOL_GDB_ID},
    )


def count_available_genesets(tiers: list[int]) -> tuple[Composed, dict]:
    """Number of gene sets in the selected curation tiers."""
    return (
        SQL("SELECT count(*) FROM production.geneset WHERE cur_id = ANY(%(tiers)s)").format(),
        {"tiers": tiers},
    )


def select_genes_of_interest(interest_table: str) -> tuple[Composed, dict]:
    """Distinct genes of interest with their species name."""
    query = SQL(
        """
        SELECT DISTINCT ON (a.ode_gene_id) a.ode_gene_id, a.ode_ref_id, b.sp_name
          FROM {interest} AS a, odestatic.species AS b
         WHERE a.sp_id = b.sp_id
         ORDER BY a.ode_gene_id
        """
    ).format(interest=_table(interest_table))
    return query, {}


def select_input_species(interest_table: str) -> tuple[Composed, dict]:
    """Distinct species names present in the genes of interest."""
    query = SQL(
        """
        SELECT DISTINCT b.sp_name
          FROM {interest} AS a, odestatic.species AS b
         WHERE a.sp_id = b.sp_id
        """
    ).format(interest=_table(interest_table))
    return query, {}


def select_matching_genesets(
    matching_table: str, tiers: list[int], min_genes: int, limit: int = 50
) -> tuple[Composed, dict]:
    """Top matching gene sets by gene-match count (then size)."""
    query = SQL(
        """
        SELECT gs_id, gs_name, genematchcount, cur_id, sp_id, gs_attribution,
               gs_abbreviation, gs_description, gs_count
          FROM {matching}
         WHERE genematchcount >= %(min_genes)s AND cur_id = ANY(%(tiers)s)
         ORDER BY genematchcount DESC, gs_count
         LIMIT %(limit)s
        """
    ).format(matching=_table(matching_table))
    return query, {"min_genes": min_genes, "tiers": tiers, "limit": limit}


def select_result_genes(
    result_table: str, min_genesets: int, limit: int = 50
) -> tuple[Composed, dict]:
    """Top result genes by how many of the matching gene sets they occur in."""
    query = SQL(
        """
        SELECT * FROM (
            SELECT DISTINCT ON (a.ode_gene_id)
                   a.ode_gene_id, b.ode_ref_id, c.sp_name, c.sp_id, a.occurrences
              FROM {result} AS a, extsrc.gene AS b, odestatic.species AS c
             WHERE a.ode_gene_id = b.ode_gene_id AND b.sp_id = c.sp_id
               AND a.occurrences >= %(min_genesets)s
        ) AS results
        ORDER BY occurrences DESC
        LIMIT %(limit)s
        """
    ).format(result=_table(result_table))
    return query, {"min_genesets": min_genesets, "limit": limit}


def select_max_occurrences(result_table: str) -> tuple[Composed, dict]:
    """The highest occurrence count among the result genes (1 row)."""
    query = SQL("SELECT occurrences FROM {result} ORDER BY occurrences DESC LIMIT 1").format(
        result=_table(result_table)
    )
    return query, {}


def select_gene_ref_ids(ode_gene_id: int) -> tuple[Composed, dict]:
    """All gene-symbol reference ids for a gene."""
    return (
        SQL(
            "SELECT ode_ref_id FROM extsrc.gene "
            "WHERE ode_gene_id = %(ode_gene_id)s AND gdb_id = %(gdb_id)s"
        ).format(),
        {"ode_gene_id": ode_gene_id, "gdb_id": GENE_SYMBOL_GDB_ID},
    )


def select_preferred_ref_id(ode_gene_id: int) -> tuple[Composed, dict]:
    """The preferred gene-symbol reference id for a gene."""
    return (
        SQL(
            "SELECT ode_ref_id FROM extsrc.gene "
            "WHERE ode_gene_id = %(ode_gene_id)s AND gdb_id = %(gdb_id)s AND ode_pref = TRUE"
        ).format(),
        {"ode_gene_id": ode_gene_id, "gdb_id": GENE_SYMBOL_GDB_ID},
    )


def count_genesets_by_tier(
    ode_gene_id: int, thresholds: Thresholds = ALL_GENES
) -> tuple[Composed, dict]:
    """Per-curation-tier gene-set counts for a gene (non-deprecated, as the run thresholds)."""
    member, params = membership_filter(thresholds, gv="gsv", gs="gs")
    query = SQL(
        """
        SELECT count(gs.gs_id) AS gs_count, gs.cur_id
          FROM production.geneset gs, extsrc.geneset_value gsv
         WHERE gs.gs_id = gsv.gs_id AND gsv.ode_gene_id = %(ode_gene_id)s
           AND gs.cur_id IS NOT NULL
           AND gs.gs_status NOT LIKE %(deprecated)s
           AND {member}
         GROUP BY gs.cur_id
         ORDER BY gs.cur_id
        """
    ).format(member=member)
    return query, {"ode_gene_id": ode_gene_id, "deprecated": "de%", **params}


def count_genesets_by_species(
    ode_gene_id: int, thresholds: Thresholds = ALL_GENES
) -> tuple[Composed, dict]:
    """Per-species gene-set counts for a gene's homology group (non-deprecated)."""
    member, params = membership_filter(thresholds, gv="gsv", gs="gs")
    query = SQL(
        """
        SELECT count(gs.gs_id) AS gs_count, gs.sp_id
          FROM production.geneset gs, extsrc.geneset_value gsv
         WHERE gs.gs_id = gsv.gs_id
           AND gsv.ode_gene_id IN
             (SELECT h1.ode_gene_id FROM extsrc.homology h1, extsrc.homology h2
               WHERE h1.hom_id = h2.hom_id AND h2.ode_gene_id = %(ode_gene_id)s)
           AND {member}
           AND gs.gs_status NOT LIKE %(deprecated)s
         GROUP BY gs.sp_id
         ORDER BY gs.sp_id
        """
    ).format(member=member)
    return query, {"ode_gene_id": ode_gene_id, "deprecated": "de%", **params}
