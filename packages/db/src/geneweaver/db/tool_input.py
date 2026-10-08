"""Resolve database state into the inputs the ported analysis tools expect.

The tools in ``geneweaver-tools`` are pure: each takes a fully-built ``ToolInput`` and
touches no database. Something has to assemble that input, and this module is where those
resolvers live (G3-798). Only ABBA had one before -- ``geneweaver.db.abba``.

Keeping the resolvers here rather than in the API means the same input can be built by
whatever ends up executing the tool, in-process today or AsyncTask later.

Access control is deliberately *not* done here. These functions answer "what is in this
gene set"; deciding whether the caller may see it belongs to the service layer, which knows
about users. Callers must gate first.
"""

from typing import Any

from geneweaver.core.enum import GeneIdentifier
from psycopg import Cursor


def _symbol(row: Any) -> str:
    """Read the gene symbol from a row under either row factory.

    The API's connection pool uses ``dict_row`` (``dependencies.py``), while parts of
    ``packages/db`` and its tests use tuple rows.
    """
    if isinstance(row, dict):
        return row["ode_ref_id"]
    return row[0]


def gene_symbols_by_geneset(cursor: Cursor, geneset_ids: list[int]) -> dict[str, list[str]]:
    """Map each gene set id to its preferred, in-threshold gene symbols.

    This is the input shape shared by the membership-based tools -- UpSet, DBSCAN,
    HyperGeometric, JaccardClustering and PhenomeMap all want "the genes in each of these
    sets".

    Uses the filter the legacy tools did: ``gdb_id = 7`` and ``ode_pref = 't'`` for the
    preferred symbol, and **``gsv_in_threshold``** for membership. That last one matters:
    every resolver in ``scripts/validation/`` filters on it, as legacy's ``TOOLSET_SQL``
    does, and without it a gene set contributes genes the legacy worker would have
    excluded. On dev, 5.7% of gene sets carry below-threshold genes, so for those sets the
    unfiltered result is a different analysis, not a rounding difference.

    Tables are schema-qualified rather than relying on ``search_path``: v3 puts ``public``
    first where legacy omits it, so an unqualified name does not necessarily resolve to the
    same table in both (see G3-827).

    :param cursor: The database cursor.
    :param geneset_ids: The gene sets to resolve, in the caller's order.
    :return: ``{geneset_id_as_str: [symbol, ...]}``, preserving input order.
    """
    memberships: dict[str, list[str]] = {str(geneset_id): [] for geneset_id in geneset_ids}
    if not geneset_ids:
        return memberships
    cursor.execute(
        """
        SELECT gv.gs_id, g.ode_ref_id
        FROM extsrc.geneset_value gv
        JOIN extsrc.gene g ON g.ode_gene_id = gv.ode_gene_id
        WHERE gv.gs_id = ANY(%(geneset_ids)s)
          AND gv.gsv_in_threshold
          AND g.gdb_id = 7
          AND g.ode_pref = 't';
        """,
        {"geneset_ids": list(geneset_ids)},
    )
    for row in cursor.fetchall():
        geneset_id, symbol = (row["gs_id"], row["ode_ref_id"]) if isinstance(row, dict) else row
        if symbol is not None:
            memberships[str(geneset_id)].append(symbol)
    return memberships


def _fields(row: Any, *names: str) -> tuple:
    """Read named columns from a row under either row factory, in the order named."""
    if isinstance(row, dict):
        return tuple(row[name] for name in names)
    return tuple(row)


def collapse_homologs(
    member_rows: list[tuple[Any, int, str]],
    homology_rows: list[tuple[int, int]],
    geneset_ids: list[int],
) -> dict[str, list[str]]:
    """Merge homologous genes into one member each, as legacy ``combine_genesets`` did.

    Legacy's "Homology: Included" treated genes sharing a homology group as the same gene
    across every gene set in the run, so a mouse and a human set overlap on their
    orthologs. Groups merge transitively (union-find over ``hom_id``): a gene in two groups
    joins both. A merged member is labelled with the sorted, distinct preferred symbols of
    its group that occur in this run, joined by ``/`` (``"DRD2/Drd2"``); a gene with no
    homolog in the run keeps its own symbol, so a same-species run changes only where
    homologous genes (paralogs in one group) occur together.

    :param member_rows: ``(gs_id, ode_gene_id, symbol)`` per in-threshold member.
    :param homology_rows: ``(ode_gene_id, hom_id)`` for those genes.
    :param geneset_ids: The gene sets, in the caller's order.
    :return: ``{geneset_id_as_str: [label, ...]}``, de-duplicated, preserving order.
    """
    parent: dict[tuple, tuple] = {}

    def find(node: tuple) -> tuple:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    present = {gene_id for _, gene_id, symbol in member_rows if symbol is not None}
    for gene_id, hom_id in homology_rows:
        if gene_id in present:
            parent[find(("gene", gene_id))] = find(("hom", hom_id))

    symbols_by_root: dict[tuple, set[str]] = {}
    for _, gene_id, symbol in member_rows:
        if symbol is not None:
            symbols_by_root.setdefault(find(("gene", gene_id)), set()).add(symbol)
    labels = {root: "/".join(sorted(symbols)) for root, symbols in symbols_by_root.items()}

    memberships: dict[str, list[str]] = {str(geneset_id): [] for geneset_id in geneset_ids}
    seen: dict[str, set[str]] = {key: set() for key in memberships}
    for geneset_id, gene_id, symbol in member_rows:
        key = str(geneset_id)
        if symbol is None or key not in memberships:
            continue
        label = labels[find(("gene", gene_id))]
        if label not in seen[key]:
            seen[key].add(label)
            memberships[key].append(label)
    return memberships


def homologous_gene_symbols_by_geneset(
    cursor: Cursor, geneset_ids: list[int]
) -> dict[str, list[str]]:
    """:func:`gene_symbols_by_geneset` with homologous genes merged across the run.

    The membership-based tools' "Homology: Included" option (legacy's default). Members are
    filtered exactly as in :func:`gene_symbols_by_geneset`; homology groups come from
    ``extsrc.homology`` by ``hom_id``, any source, as legacy ``TOOLSET_SQL[1]`` read them.
    See :func:`collapse_homologs` for how groups become members.

    :param cursor: The database cursor.
    :param geneset_ids: The gene sets to resolve, in the caller's order.
    :return: ``{geneset_id_as_str: [label, ...]}``, preserving input order.
    """
    if not geneset_ids:
        return {}
    cursor.execute(
        """
        SELECT gv.gs_id, g.ode_gene_id, g.ode_ref_id
        FROM extsrc.geneset_value gv
        JOIN extsrc.gene g ON g.ode_gene_id = gv.ode_gene_id
        WHERE gv.gs_id = ANY(%(geneset_ids)s)
          AND gv.gsv_in_threshold
          AND g.gdb_id = 7
          AND g.ode_pref = 't';
        """,
        {"geneset_ids": list(geneset_ids)},
    )
    member_rows = [_fields(row, "gs_id", "ode_gene_id", "ode_ref_id") for row in cursor.fetchall()]
    gene_ids = sorted({gene_id for _, gene_id, _ in member_rows})
    homology_rows: list[tuple] = []
    if gene_ids:
        cursor.execute(
            """
            SELECT ode_gene_id, hom_id
            FROM extsrc.homology
            WHERE ode_gene_id = ANY(%(gene_ids)s);
            """,
            {"gene_ids": gene_ids},
        )
        homology_rows = [_fields(row, "ode_gene_id", "hom_id") for row in cursor.fetchall()]
    return collapse_homologs(member_rows, homology_rows, geneset_ids)


def geneset_platforms(cursor: Cursor, geneset_ids: list[int]) -> dict[int, tuple[int, int]]:
    """``{gs_id: (sp_id, gs_gene_id_type)}`` -- what pairwise deletion decides on.

    A positive ``gs_gene_id_type`` is the microarray platform (``odestatic.platform.pf_id``)
    the set was measured on; a negative one is a gene identifier type. Promoted from legacy
    ``TOOLSET_SQL[3]``, for every gene set at once rather than one query per pair.
    """
    if not geneset_ids:
        return {}
    cursor.execute(
        """
        SELECT gs_id, sp_id, gs_gene_id_type
        FROM production.geneset
        WHERE gs_id = ANY(%(geneset_ids)s);
        """,
        {"geneset_ids": list(geneset_ids)},
    )
    rows = (_fields(row, "gs_id", "sp_id", "gs_gene_id_type") for row in cursor.fetchall())
    return {gs_id: (sp_id, gene_id_type) for gs_id, sp_id, gene_id_type in rows}


def platform_gene_symbols(cursor: Cursor, platform_id: int) -> set[str]:
    """Preferred gene symbols a microarray platform (or platform set) can measure.

    Legacy ``TOOLSET_SQL[5]``/``[6]`` in gene symbols rather than ``ode_gene_id``: the
    membership-based tools compare symbols, so the platform's gene space has to be in the
    same space. A platform id matches the platform itself or any platform in that set
    (``pf_set``), as legacy's ``m.pf_id = %s OR m.pf_set = %s`` did.
    """
    cursor.execute(
        """
        SELECT DISTINCT g.ode_ref_id
        FROM extsrc.probe2gene p2g
        JOIN odestatic.probe p ON p.prb_id = p2g.prb_id
        JOIN odestatic.platform m ON m.pf_id = p.pf_id
        JOIN extsrc.gene g ON g.ode_gene_id = p2g.ode_gene_id
        WHERE (m.pf_id = %(platform_id)s OR m.pf_set = %(platform_id)s)
          AND g.gdb_id = 7
          AND g.ode_pref = 't';
        """,
        {"platform_id": platform_id},
    )
    return {symbol for symbol in map(_symbol, cursor.fetchall()) if symbol is not None}


def membership_rows(cursor: Cursor, geneset_ids: list[int]) -> list[list]:
    """``(gs_id, ode_gene_id, ode_ref_id)`` for in-threshold members -- Combine's matrix.

    Promoted from legacy ``TOOLSET_SQL[0]``, schema-qualified.
    """
    cursor.execute(
        """
        SELECT gv.gs_id, gv.ode_gene_id, g.ode_ref_id
        FROM extsrc.geneset_value gv
        JOIN extsrc.gene g ON g.ode_gene_id = gv.ode_gene_id
        WHERE gv.gsv_in_threshold AND gv.gs_id = ANY(%(geneset_ids)s) AND g.ode_pref;
        """,
        {"geneset_ids": list(geneset_ids)},
    )
    return [
        list(row.values()) if isinstance(row, dict) else list(row) for row in cursor.fetchall()
    ]


def homology_pairs(cursor: Cursor, geneset_ids: list[int]) -> list[list]:
    """``(left_ode_gene_id, right_ode_gene_id, hom_id)`` across the given gene sets.

    Promoted from legacy ``TOOLSET_SQL[1]``, schema-qualified. Combine and BooleanAlgebra
    use it to treat orthologous genes as the same gene across species.
    """
    cursor.execute(
        """
        SELECT a.ode_gene_id AS left_ode_gene_id,
               b.ode_gene_id AS right_ode_gene_id,
               a.hom_id
        FROM extsrc.homology a, extsrc.homology b
        WHERE a.hom_id = b.hom_id
          AND a.ode_gene_id <> b.ode_gene_id
          AND a.ode_gene_id IN (SELECT DISTINCT ode_gene_id FROM extsrc.geneset_value
                                WHERE gsv_in_threshold AND gs_id = ANY(%(geneset_ids)s))
          AND b.ode_gene_id IN (SELECT DISTINCT ode_gene_id FROM extsrc.geneset_value
                                WHERE gsv_in_threshold AND gs_id = ANY(%(geneset_ids)s))
        GROUP BY left_ode_gene_id, right_ode_gene_id, a.hom_id;
        """,
        {"geneset_ids": list(geneset_ids)},
    )
    return [
        list(row.values()) if isinstance(row, dict) else list(row) for row in cursor.fetchall()
    ]


def geneset_labels(cursor: Cursor, geneset_ids: list[int]) -> list[list]:
    """``(gs_id, gs_name, gs_abbreviation)`` -- Combine's column headers.

    Promoted from legacy ``TOOLSET_SQL[2]``, schema-qualified.
    """
    cursor.execute(
        """
        SELECT gs_id, gs_name, gs_abbreviation
        FROM production.geneset
        WHERE gs_id = ANY(%(geneset_ids)s);
        """,
        {"geneset_ids": list(geneset_ids)},
    )
    return [
        list(row.values()) if isinstance(row, dict) else list(row) for row in cursor.fetchall()
    ]


def jaccard_distributions(cursor: Cursor) -> list[dict]:
    """Null distributions JaccardSimilarity turns similarity into a p-value with.

    Grouped into one distribution per ``(set_size1, set_size2, homology)``, which is the
    shape ``JaccardDistribution`` wants.

    Note on the data: the roadmap records this table as empty across local/dev/sqa, which
    is why the tool was treated as inert. On dev it holds 2,731 rows -- so the claim is at
    least out of date there. Coverage is what matters, not row count: a pair whose sizes
    have no distribution still gets no p-value, so callers should check the result rather
    than assume.
    """
    cursor.execute(
        """
        SELECT set_size1, set_size2, homology, jaccard_coef, frequency
        FROM extsrc.jaccard_distribution_results
        ORDER BY set_size1, set_size2, jaccard_coef;
        """
    )
    grouped: dict[tuple, list[tuple[float, int]]] = {}
    for row in cursor.fetchall():
        if isinstance(row, dict):
            key = (row["set_size1"], row["set_size2"], row["homology"])
            grouped.setdefault(key, []).append((float(row["jaccard_coef"]), int(row["frequency"])))
        else:
            grouped.setdefault((row[0], row[1], row[2]), []).append((float(row[3]), int(row[4])))
    return [
        {"set_size1": a, "set_size2": b, "homology": hom, "frequencies": freqs}
        for (a, b, hom), freqs in grouped.items()
    ]


def species_by_geneset(cursor: Cursor, geneset_ids: list[int]) -> dict[int, int]:
    """Map each gene set id to its species id.

    MSET compares two gene sets against a shared gene universe, which is per species, so
    the caller has to know the species before it can resolve one.

    :param cursor: The database cursor.
    :param geneset_ids: The gene sets to look up.
    :return: ``{geneset_id: sp_id}``, omitting ids that do not exist.
    """
    if not geneset_ids:
        return {}
    cursor.execute(
        """
        SELECT gs_id, sp_id
        FROM production.geneset
        WHERE gs_id = ANY(%(geneset_ids)s);
        """,
        {"geneset_ids": list(geneset_ids)},
    )
    rows = cursor.fetchall()
    if rows and isinstance(rows[0], dict):
        return {row["gs_id"]: row["sp_id"] for row in rows}
    return {row[0]: row[1] for row in rows}


def gene_universe(
    cursor: Cursor,
    species_id: int,
    gene_id_type: int = int(GeneIdentifier.GENE_SYMBOL),
) -> list[str]:
    """Every gene identifier GeneWeaver knows for a species -- MSET's background.

    This is the **full gene space**, not the genes appearing in curated gene sets. Legacy
    used the latter, precomputed into ~600 ``*BG.txt`` files, which meant a gene unique to a
    Tier-IV set sat outside its own background and MSET refused the run (GWC-51 / G3-783);
    the files also went stale on every gene reload (GWC-45 / G3-766). Resolving here removes
    both, and the regeneration job and per-environment storage with them (G3-784).

    ``gene_id_type`` defaults to gene symbols because that is the space
    :func:`gene_symbols_by_geneset` returns the member lists in, and MSET requires each list
    to be a subset of its background. Legacy keyed the background file off the *gene set's*
    ``gene_id_type`` while fetching members as symbols, so any set whose type was not Gene
    Symbol produced a background the members could not possibly belong to -- which is part of
    why 450 of those 602 files were empty. Pass something else only alongside member lists
    resolved in that same space.

    :param cursor: The database cursor.
    :param species_id: The species whose gene space to return.
    :param gene_id_type: ``gdb_id`` of the identifier space; gene symbols by default.
    :return: Sorted, de-duplicated identifiers.
    """
    cursor.execute(
        """
        SELECT DISTINCT ode_ref_id
        FROM extsrc.gene
        WHERE sp_id = %(species_id)s
          AND gdb_id = %(gene_id_type)s
          AND ode_pref = 't'
        ORDER BY ode_ref_id;
        """,
        {"species_id": species_id, "gene_id_type": gene_id_type},
    )
    return [_symbol(row) for row in cursor.fetchall()]


def homolog_annotations(
    cursor: Cursor, geneset_ids: list[int], species_ids: list[int]
) -> list[list]:
    """Gene membership annotated with Homologene groups -- BooleanAlgebra's input.

    Rows are ``(hom_source_id, ode_gene_id, ode_ref_id, sp_id, gs_id, gs_abbreviation)``.
    ``hom_source_id`` is NULL for a gene with no homolog in the requested species, which is
    load-bearing: BooleanAlgebra keys on it to decide whether a gene can be identified
    across species or only within one, so dropping those rows changes the answer.

    This is **not** the same as :func:`homology_pairs`, which returns ortholog pairs for
    Combine. Promoted from legacy ``GET_HOMOLOGS_SQL`` (``CS_Boolean/service.py``), with two
    changes: the tables are schema-qualified rather than relying on ``search_path``
    (G3-827), and the gene set ids and species are bound as parameters instead of being
    formatted into the string -- legacy interpolated them, which is the pattern `CLAUDE.md`
    forbids.

    Its filter is legacy's, ``gdb_id = 7`` included: one row per gene, its preferred symbol.
    ``ode_pref`` alone is not one per gene -- on dev a gene can have a preferred UniGene id
    as well (``Ppp1ccb`` and ``Mm.334198``) -- and BooleanAlgebra counts rows, so a gene in
    one set with two identifiers passed "in at least 2 sets" (G3-830).

    :param cursor: The database cursor.
    :param geneset_ids: The gene sets whose members to return.
    :param species_ids: Species to look for homologs in.
    """
    cursor.execute(
        """
        SELECT hom.hom_source_id, g.ode_gene_id, g.ode_ref_id, g.sp_id,
               gv.gs_id, gs.gs_abbreviation
        FROM extsrc.gene g
        JOIN extsrc.geneset_value gv ON gv.ode_gene_id = g.ode_gene_id
        JOIN production.geneset gs ON gs.gs_id = gv.gs_id
        LEFT JOIN (
            SELECT ode_gene_id, hom_source_id
            FROM extsrc.homology
            WHERE hom_source_name = 'Homologene'
              AND hom_source_id IN (
                  SELECT h.hom_source_id
                  FROM extsrc.homology h
                  JOIN extsrc.geneset_value gv2 ON gv2.ode_gene_id = h.ode_gene_id
                  WHERE gv2.gs_id = ANY(%(geneset_ids)s) AND gv2.gsv_in_threshold
              )
              AND sp_id = ANY(%(species_ids)s)
        ) hom ON g.ode_gene_id = hom.ode_gene_id
        WHERE gv.gs_id = ANY(%(geneset_ids)s)
          AND gv.gsv_in_threshold
          AND g.gdb_id = 7
          AND g.ode_pref = TRUE
        ORDER BY hom.hom_source_id, gv.gs_id;
        """,
        {"geneset_ids": list(geneset_ids), "species_ids": list(species_ids)},
    )
    return [
        list(row.values()) if isinstance(row, dict) else list(row) for row in cursor.fetchall()
    ]
