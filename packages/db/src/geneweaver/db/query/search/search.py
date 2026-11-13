"""Full general search of Geneweaver Database."""

from collections.abc import Sequence
from datetime import date

from geneweaver.db.query.geneset.const import GENESET_FIELDS
from geneweaver.db.query.geneset.utils import (
    format_select_query,
    restrict_score_type,
    restrict_species,
    restrict_tier,
)
from geneweaver.db.query.search import const
from geneweaver.db.query.search.utils import search
from geneweaver.db.query.utils import add_op_filters, construct_filters
from geneweaver.db.utils import (
    GenesetScoreTypeOrScoreTypes,
    GenesetTierOrTiers,
    SpeciesOrSpeciesSet,
    limit_and_offset,
)
from psycopg.sql import SQL, Composed

#: Columns search results can be sorted by (G3-777), by the name the API takes. Only these
#: fragments reach the SQL, so a sort key is never formatted in from the request.
SORT_COLUMNS: dict[str, SQL] = {
    "id": SQL("geneset.gs_id"),
    "name": SQL("lower(geneset.gs_name)"),
    "size": SQL("geneset.gs_count"),
    "species": SQL("(SELECT sp.sp_name FROM odestatic.species sp WHERE sp.sp_id = geneset.sp_id)"),
    "tier": SQL("geneset.cur_id"),
    "score_type": SQL("geneset.gs_threshold_type"),
    "created": SQL("geneset.gs_created"),
    "updated": SQL("geneset.gs_updated"),
}

SORT_ORDERS = {"asc": SQL("ASC"), "desc": SQL("DESC")}

#: How many genes one search takes (G3-832): each adds a lookup on ``geneset_value``.
MAX_GENES = 5

#: Identifier source of gene symbols, the name a matched gene is shown by.
_GENE_SYMBOL_GDB_ID = 7


def _gene_ids(key: str) -> Composed:
    """Every gene recorded under the searched identifier (symbol, Ensembl, MGI, ...).

    Matched ignoring case and species, so "Drd2" finds mouse Drd2 and human DRD2. ``key``
    names the bound parameter holding the identifier.
    """
    return SQL(
        "SELECT g.ode_gene_id FROM extsrc.gene g WHERE lower(g.ode_ref_id) = lower(%({key})s)"
    ).format(key=SQL(key))


def _gene_and_homolog_ids(key: str) -> Composed:
    """`_gene_ids`, plus every gene sharing a homology group with them (G3-834).

    As ABBA widens its input genes: the genes' ``hom_id``s, then every gene in those groups,
    any species. A gene with no homology row is only itself.
    """
    return SQL(
        "{direct} UNION SELECT h2.ode_gene_id FROM extsrc.homology h1 "
        "JOIN extsrc.homology h2 ON h2.hom_id = h1.hom_id "
        "WHERE h1.ode_gene_id IN ({direct})"
    ).format(direct=_gene_ids(key))


def _searched_ids(key: str, homology: bool) -> Composed:
    """The genes a gene set may hold to match the identifier under ``key``."""
    return _gene_and_homolog_ids(key) if homology else _gene_ids(key)


def gene_threshold_filter(
    p_value: float | None = None,
    q_value: float | None = None,
    correlation_low: float | None = None,
    correlation_high: float | None = None,
    effect_low: float | None = None,
    effect_high: float | None = None,
) -> tuple[Composed | None, dict]:
    """The searched gene's score passes the cutoff for its gene set's score type (G3-764).

    A gene set has one score type, so cutoffs for several types are an OR across types,
    each applied only to gene sets of its own type. The direction follows the type, as in
    `geneweaver.core.threshold.check_threshold`: a p- or q-value at or below its cutoff, a
    correlation or effect inside its range (either end may be open). Gene sets of a type
    with no cutoff -- binary ones always -- do not match.

    :return: The predicate over ``gsv`` (``extsrc.geneset_value``) and ``geneset``, or
        ``None`` when no cutoff is given.
    """
    clauses: list[Composed] = []
    params: dict = {}
    if p_value is not None:
        clauses.append(SQL("(geneset.gs_threshold_type = 1 AND gsv.gsv_value <= %(p_value)s)"))
        params["p_value"] = p_value
    if q_value is not None:
        clauses.append(SQL("(geneset.gs_threshold_type = 2 AND gsv.gsv_value <= %(q_value)s)"))
        params["q_value"] = q_value
    for type_id, name, low, high in (
        (4, "correlation", correlation_low, correlation_high),
        (5, "effect", effect_low, effect_high),
    ):
        if low is None and high is None:
            continue
        bounds = [SQL("geneset.gs_threshold_type = {type_id}").format(type_id=type_id)]
        if low is not None:
            bounds.append(SQL("gsv.gsv_value >= %({key})s").format(key=SQL(f"{name}_low")))
            params[f"{name}_low"] = low
        if high is not None:
            bounds.append(SQL("gsv.gsv_value <= %({key})s").format(key=SQL(f"{name}_high")))
            params[f"{name}_high"] = high
        clauses.append(SQL("(") + SQL(" AND ").join(bounds) + SQL(")"))
    if not clauses:
        return None, params
    return SQL("(") + SQL(" OR ").join(clauses) + SQL(")"), params


def _holds_gene(key: str, homology: bool, predicate: Composed | None = None) -> Composed:
    """The gene set holds the gene under ``key``, or with ``homology`` one of its homologs.

    And that gene's score passes ``predicate``, if given.
    """
    query = SQL(
        "EXISTS (SELECT 1 FROM extsrc.geneset_value gsv WHERE gsv.gs_id = geneset.gs_id "
        "AND gsv.ode_gene_id IN ({gene_ids})"
    ).format(gene_ids=_searched_ids(key, homology))
    if predicate is not None:
        query = SQL(" ").join([query, SQL("AND"), predicate])
    return query + SQL(")")


def _gene_keys(gene: str | Sequence[str] | None) -> list[str]:
    """The searched genes' parameter names.

    ``gene`` for one, as before; else ``gene_0``, ``gene_1``, ...
    """
    if gene is None:
        return []
    genes = [gene] if isinstance(gene, str) else list(gene)
    if len(genes) > MAX_GENES:
        raise ValueError(f"At most {MAX_GENES} genes per search, not {len(genes)}.")
    return ["gene"] if len(genes) == 1 else [f"gene_{i}" for i in range(len(genes))]


def _gene_params(gene: str | Sequence[str]) -> dict:
    """The genes bound under the names `_gene_keys` gives them."""
    genes = [gene] if isinstance(gene, str) else list(gene)
    return dict(zip(_gene_keys(gene), genes, strict=True))


def _matched_gene(key: str, homology: bool, predicate: Composed | None) -> Composed:
    """Which gene of the gene set matched the identifier under ``key``, as a JSON object.

    ``{"query": <as typed>, "gene": <its symbol>, "homolog": <not the typed gene itself>,
    "value": <its score>}``, or NULL when the gene set does not hold it (an ``any`` search).
    With several candidates (a gene and its homologs, or two genes under one identifier), the
    one whose score passes the cutoffs comes first, then the typed gene over a homolog, then
    the symbol in alphabetical order, so the choice does not change between requests.
    """
    ordering = [SQL("(gsv.ode_gene_id IN ({direct})) DESC").format(direct=_gene_ids(key))]
    if predicate is not None:
        ordering.insert(0, SQL("({predicate}) DESC").format(predicate=predicate))
    ordering.append(SQL("sym.ode_ref_id"))
    return SQL(
        "(SELECT jsonb_build_object("
        "'query', %({key})s::text, "
        "'gene', coalesce(sym.ode_ref_id, %({key})s::text), "
        "'homolog', gsv.ode_gene_id NOT IN ({direct}), "
        "'value', gsv.gsv_value) "
        "FROM extsrc.geneset_value gsv "
        "LEFT JOIN extsrc.gene sym ON sym.ode_gene_id = gsv.ode_gene_id "
        "AND sym.gdb_id = {symbol} AND sym.ode_pref "
        "WHERE gsv.gs_id = geneset.gs_id AND gsv.ode_gene_id IN ({gene_ids}) "
        "ORDER BY {ordering} LIMIT 1)"
    ).format(
        key=SQL(key),
        direct=_gene_ids(key),
        symbol=_GENE_SYMBOL_GDB_ID,
        gene_ids=_searched_ids(key, homology),
        ordering=SQL(", ").join(ordering),
    )


def _matched_genes(keys: list[str], homology: bool, predicate: Composed | None) -> Composed:
    """The ``matched_genes`` result column: `_matched_gene` for each searched gene it holds."""
    candidates = SQL(", ").join(
        SQL("({matched})").format(matched=_matched_gene(key, homology, predicate)) for key in keys
    )
    return SQL(
        "(SELECT coalesce(jsonb_agg(m), '[]'::jsonb) FROM (VALUES {candidates}) AS v(m) "
        "WHERE m IS NOT NULL) AS matched_genes"
    ).format(candidates=candidates)


def _readable(filters: list, params: dict, user_id: int | None) -> None:
    """Only gene sets ``user_id`` may read: ``production.geneset_is_readable2``, set-based.

    The function is right but costs ~15 ms for each private gene set it has to decide: it
    re-runs the user's group and project lookups for every row. A search that stops at its
    first page barely notices; a sorted one checks every match -- 10,825 for "dopamine",
    2,616 of them private Tier V sets, 40 s. Here the same six cases are written once, with
    the user's groups, shared projects and admin flag looked up once per query.

    Keep it in step with the function (``pg_get_functiondef('production.geneset_is_readable2'
    ::regproc)``): the user owns the set; the set is public (``gs_groups = '0'``) or in a
    public tier (``cur_id < 5``); one of the user's groups shares it; one of the user's groups
    shares a project holding it; or the user is an admin or curator (``usr_admin > 0``), who
    sees every private gene set, as in legacy. Checked equal to the function on dev for
    anonymous, grouped, project-sharing, admin, curator and ordinary users.
    """
    if user_id is None:
        return
    filters.append(
        SQL(
            """(geneset.usr_id = %(is_readable_by)s
            OR geneset.gs_groups = '0'
            OR geneset.cur_id < 5
            OR ('{' || geneset.gs_groups || '}')::integer[] && ARRAY(
                SELECT u2g.grp_id FROM production.usr2grp u2g
                 WHERE u2g.usr_id = %(is_readable_by)s)
            OR geneset.gs_id IN (
                SELECT p2g.gs_id FROM production.project2geneset p2g
                  JOIN production.project p ON p.pj_id = p2g.pj_id
                  JOIN production.usr2grp u2g
                    ON u2g.grp_id = ANY(('{' || p.pj_groups || '}')::integer[])
                 WHERE u2g.usr_id = %(is_readable_by)s)
            OR EXISTS (
                SELECT 1 FROM production.usr u
                 WHERE u.usr_admin > 0 AND u.usr_id = %(is_readable_by)s))"""
        )
    )
    params["is_readable_by"] = user_id


def genesets(
    search_text: str | None = None,
    is_readable_by: int | None = None,
    publication_id: int | None = None,
    pubmed_id: int | None = None,
    species: SpeciesOrSpeciesSet | None = None,
    curation_tier: GenesetTierOrTiers | None = None,
    score_type: GenesetScoreTypeOrScoreTypes | None = None,
    lte_count: int | None = None,
    gte_count: int | None = None,
    created_before: date | None = None,
    created_after: date | None = None,
    updated_before: date | None = None,
    updated_after: date | None = None,
    limit: int | None = 25,
    offset: int | None = 0,
    _status: str | None = "normal",
    sort_by: str | None = None,
    sort_order: str = "asc",
    gene: str | Sequence[str] | None = None,
    gene_match: str = "all",
    homology: bool = False,
    p_value: float | None = None,
    q_value: float | None = None,
    correlation_low: float | None = None,
    correlation_high: float | None = None,
    effect_low: float | None = None,
    effect_high: float | None = None,
    threshold_mode: str = "only",
    gs_id: int | None = None,
) -> tuple[Composed, dict]:
    """Search genesets using all relevant metadata fields.

    :param search_text: Return genesets that match this search text.
    :param is_readable_by: A user ID to check if the user can read the results.
    :param publication_id: Show only results with this publication ID (internal).
    :param pubmed_id: Show only results with this PubMed ID.
    :param species: Show only results associated with this species.
    :param curation_tier: Show only results of this curation tier.
    :param score_type: Show only results with given score type.
    :param lte_count: less than or equal count.
    :param gte_count: greater than or equal count.
    :param created_before: Show only results created before this date.
    :param created_after: Show only results updated before this date.
    :param updated_before: Show only results updated before this date.
    :param updated_after: Show only results updated after this date.
    :param limit: Limit the number of results.
    :param offset: Offset the results.
    :param _status: Show only results with this status. Default is "normal".
    :param sort_by: A key of `SORT_COLUMNS`; unsorted when None (G3-777).
    :param sort_order: "asc" or "desc".
    :param gene: Show only gene sets holding this gene, by any of its identifiers (G3-764),
        or these genes, at most `MAX_GENES` (G3-832). Each result then says which of its
        genes matched (``matched_genes``).
    :param gene_match: With several genes: "all" keeps gene sets holding every one, "any"
        those holding at least one.
    :param homology: Also match each gene's homologs, in any species (G3-834).
    :param p_value: With ``gene``: keep p-value gene sets where its value is at most this.
    :param q_value: As ``p_value``, for q-value gene sets.
    :param correlation_low: With ``gene``: keep correlation gene sets where its value is at
        least this (and at most ``correlation_high``).
    :param correlation_high: The upper end of that range.
    :param effect_low: As ``correlation_low``, for effect gene sets.
    :param effect_high: As ``correlation_high``, for effect gene sets.
    :param threshold_mode: "only" returns just the gene sets whose score passes; "first"
        returns every gene set holding the gene, those that pass first. With several genes,
        "first" orders by how many of them pass, so gene sets where all pass lead.
    :param gs_id: Only this gene set: how a typed id is looked up, under the search's rule.
    """
    matches, ordering, params = _matches(
        search_text=search_text,
        is_readable_by=is_readable_by,
        publication_id=publication_id,
        pubmed_id=pubmed_id,
        species=species,
        curation_tier=curation_tier,
        score_type=score_type,
        lte_count=lte_count,
        gte_count=gte_count,
        created_before=created_before,
        created_after=created_after,
        updated_before=updated_before,
        updated_after=updated_after,
        _status=_status,
        gene=gene,
        gene_match=gene_match,
        homology=homology,
        p_value=p_value,
        q_value=q_value,
        correlation_low=correlation_low,
        correlation_high=correlation_high,
        effect_low=effect_low,
        effect_high=effect_high,
        threshold_mode=threshold_mode,
        gs_id=gs_id,
    )
    if gene is None:
        query = format_select_query() + matches
    else:
        passes, _ = gene_threshold_filter(
            p_value, q_value, correlation_low, correlation_high, effect_low, effect_high
        )
        query = (
            SQL("SELECT")
            + SQL(",").join([*GENESET_FIELDS, _matched_genes(_gene_keys(gene), homology, passes)])
            + SQL("FROM geneset")
            + matches
        )

    if sort_by is not None:
        ordering.append(
            SQL(" ").join([SORT_COLUMNS[sort_by], SORT_ORDERS[sort_order], SQL("NULLS LAST")])
        )
    # Always ordered, the id last: without an ORDER BY, Postgres may return the rows of
    # successive pages in different orders, so paging repeated some gene sets and skipped
    # others (on dev, 499 repeats in 2,000 rows of a gene search, 70 of a text search).
    # "+ 0" keeps the planner from walking the primary key in id order and testing every
    # gene set until it has a page: fast for common words, but 1.7 s for a rare one or an
    # id, 7 s cold. Finding the matches first, then sorting them, took 0.02-0.36 s on dev
    # for every search tried, "gene" (161k matches) included.
    query += SQL("ORDER BY") + SQL(", ").join([*ordering, SQL("geneset.gs_id + 0")])

    query = limit_and_offset(query, limit, offset).join(" ")

    return query, params


#: `genesets` arguments that page or order the matches without changing which they are.
_PAGING_AND_SORTING = ("limit", "offset", "sort_by", "sort_order")


def count_genesets(**search_args: object) -> tuple[Composed, dict]:
    """How many gene sets `genesets` finds across all its pages, for the paginator's total.

    Counted over the same joins and filters as the page query, so the total is the number of
    rows the pages walk through and cannot drift from them. It takes `genesets`' arguments;
    paging and sorting change no count, so they are ignored.
    """
    for key in _PAGING_AND_SORTING:
        search_args.pop(key, None)
    matches, _, params = _matches(**search_args)
    return (SQL("SELECT count(*) AS total FROM geneset") + matches).join(" "), params


def _matches(
    search_text: str | None = None,
    is_readable_by: int | None = None,
    publication_id: int | None = None,
    pubmed_id: int | None = None,
    species: SpeciesOrSpeciesSet | None = None,
    curation_tier: GenesetTierOrTiers | None = None,
    score_type: GenesetScoreTypeOrScoreTypes | None = None,
    lte_count: int | None = None,
    gte_count: int | None = None,
    created_before: date | None = None,
    created_after: date | None = None,
    updated_before: date | None = None,
    updated_after: date | None = None,
    _status: str | None = "normal",
    gene: str | Sequence[str] | None = None,
    gene_match: str = "all",
    homology: bool = False,
    p_value: float | None = None,
    q_value: float | None = None,
    correlation_low: float | None = None,
    correlation_high: float | None = None,
    effect_low: float | None = None,
    effect_high: float | None = None,
    threshold_mode: str = "only",
    gs_id: int | None = None,
) -> tuple[Composed, list[Composed], dict]:
    """The joins and WHERE clause after ``FROM geneset`` that pick the search's gene sets.

    Shared by `genesets` and `count_genesets`. Also returns the ordering the matching itself
    implies (``threshold_mode="first"`` puts passing gene sets first), which only
    `genesets` uses. Arguments as `genesets` documents them.
    """
    if gene_match not in ("all", "any"):
        raise ValueError(f"gene_match must be 'all' or 'any', not {gene_match!r}.")
    params = {}
    filtering = []

    query = SQL("")
    # The text index and publication fields live in the search view; a gene-only search
    # (G3-764) needs neither, so it does not join the view's ~261k rows.
    if search_text is not None or publication_id is not None or pubmed_id is not None:
        query += SQL("JOIN geneset_search ON geneset_search.gs_id = geneset.gs_id")

    _readable(filtering, params, is_readable_by)
    filtering, params = search(filtering, params, const.SEARCH_COMBINED_COL, search_text)
    filtering, params = restrict_tier(filtering, params, curation_tier)
    filtering, params = restrict_score_type(filtering, params, score_type)
    filtering, params = restrict_species(filtering, params, species)

    filtering, params = add_op_filters(
        filtering,
        params,
        lte_count=lte_count,
        gte_count=gte_count,
        created_before=created_before,
        created_after=created_after,
        updated_before=updated_before,
        updated_after=updated_after,
        table="geneset",
    )

    filtering, params = construct_filters(
        filtering,
        params,
        {
            "gs_status": _status,
        },
        table="geneset",
    )

    filtering, params = construct_filters(
        filtering,
        params,
        {
            "pub_id": publication_id,
            "pub_pubmed": str(pubmed_id) if pubmed_id is not None else None,
        },
        table="geneset_search",
    )

    if gs_id is not None:
        filtering.append(SQL("geneset.gs_id = %(gs_id)s"))
        params["gs_id"] = gs_id

    ordering: list[Composed] = []
    if gene is not None:
        keys = _gene_keys(gene)
        params.update(_gene_params(gene))
        passes, threshold_params = gene_threshold_filter(
            p_value, q_value, correlation_low, correlation_high, effect_low, effect_high
        )
        params.update(threshold_params)
        joiner = SQL(" OR ") if gene_match == "any" else SQL(" AND ")
        held = passes if passes is not None and threshold_mode != "first" else None
        filtering.append(
            SQL("(") + joiner.join(_holds_gene(key, homology, held) for key in keys) + SQL(")")
        )
        if passes is not None and threshold_mode == "first":
            if len(keys) == 1:
                ordering.append(
                    SQL(" ").join([_holds_gene(keys[0], homology, passes), SQL("DESC")])
                )
            else:
                # How many of the genes pass: gene sets where every one does lead.
                passing = SQL(" + ").join(
                    SQL("({holds})::int").format(holds=_holds_gene(key, homology, passes))
                    for key in keys
                )
                ordering.append(SQL("({passing}) DESC").format(passing=passing))

    if len(filtering) > 0:
        query += SQL("WHERE") + SQL("AND").join(filtering)

    return query, ordering, params
