"""ABBA association lookup (gene <-> gene-set association explorer).

Replaces the legacy ``ABBA`` Celery task with a versioned, testable db-layer function.
ABBA expands a set of input genes by homology, finds the gene sets that contain those
"genes of interest", and reports the genes that recur across those gene sets, plus the
metadata the UI needs (matching gene sets, per-tier and per-species counts, ref-id maps).

It is a multi-step SQL pipeline over session temp tables, so the heavy work stays in
Postgres; this function orchestrates the steps and returns the structured results. The
caller owns the transaction/commit. Pure rendering from the legacy tool (the JSON file
dump, the zero-padding/list-reshaping for the bar chart) is dropped -- raw counts are
returned and the UI can shape them.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from uuid import uuid4

from geneweaver.db.query import abba as q
from geneweaver.db.query.membership import ALL_GENES, Thresholds
from psycopg import Cursor, errors


class ABBADeadlineExceeded(TimeoutError):
    """The search ran out of its time budget (``deadline``) before it finished."""


@dataclass
class ABBAResult:
    """Structured ABBA results (the legacy ``_results`` dict, minus presentation)."""

    available_genes: int = 0
    available_genesets: int = 0
    genes_of_interest: list = field(default_factory=list)
    input_species: list = field(default_factory=list)
    geneset_results: list = field(default_factory=list)
    gene_results: list = field(default_factory=list)
    max_occurrences: list = field(default_factory=list)
    # ode_gene_id -> all gene-symbol ref ids
    ode_mapping: dict = field(default_factory=dict)
    # ode_gene_id -> preferred gene-symbol ref id
    preferred_mapping: dict = field(default_factory=dict)
    # ode_gene_id -> {cur_id -> geneset count}
    tier_counts: dict = field(default_factory=dict)
    # ode_gene_id -> {sp_id -> geneset count}
    species_counts: dict = field(default_factory=dict)


def abba(
    cursor: Cursor,
    input_genes: list[str],
    *,
    geneset_ids: list[int] | None = None,
    species_ids: list[int],
    tiers: list[int],
    user_id: int = 0,
    include_homology: bool = True,
    min_genes: int | None = None,
    min_genesets: int = 0,
    result_limit: int = 50,
    thresholds: Thresholds = ALL_GENES,
    deadline: float | None = None,
    statement_timeout_seconds: float | None = None,
) -> ABBAResult:
    """Run the ABBA association pipeline and return the structured results.

    :param cursor: a **tuple-row** database cursor (rows are read by position), inside a
        transaction the caller owns. The four temp tables are ``ON COMMIT DROP``, so they
        last until that transaction ends: on an autocommit connection, open one with
        ``connection.transaction()`` first, or each table vanishes as it is created.
    :param input_genes: text-supplied gene reference ids (symbols); case-insensitive.
    :param geneset_ids: gene sets whose member genes are added to the input genes.
    :param species_ids: species to restrict genes/gene sets to.
    :param tiers: curation tiers (``cur_id``) to include.
    :param user_id: user whose group memberships gate private gene-set visibility.
    :param include_homology: expand the input genes to their homology groups.
    :param min_genes: minimum ``geneMatchCount`` for a gene set (``None`` = auto).
    :param min_genesets: minimum occurrences for a result gene.
    :param result_limit: row cap for the matching-gene-set and result-gene lists.
    :param thresholds: which of each gene set's genes count, in every step that reads
        membership: every gene by default (`geneweaver.db.query.membership`).
    :param deadline: a ``time.monotonic()`` instant the whole search must finish by. A
        statement timeout bounds each query alone, and the search runs ~20 statements plus
        4 per result gene, so without this a slow database can keep it going far past what
        its caller waits for. Each statement's timeout shrinks to the time left, capped at
        ``statement_timeout_seconds``.
    :raises ABBADeadlineExceeded: If the search would run past ``deadline``.
    """
    geneset_ids = geneset_ids or []

    def run(query: tuple) -> None:
        if deadline is not None:
            left = deadline - time.monotonic()
            if left <= 0:
                raise ABBADeadlineExceeded("The ABBA search ran out of time.")
            cap = (
                left if statement_timeout_seconds is None else min(left, statement_timeout_seconds)
            )
            cursor.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                (f"{max(1, int(cap * 1000))}ms",),
            )
        try:
            cursor.execute(*query)
        except errors.QueryCanceled as error:
            if deadline is not None and deadline - time.monotonic() <= 1:
                raise ABBADeadlineExceeded("The ABBA search ran out of time.") from error
            raise

    if geneset_ids:
        run(q.ref_ids_for_genesets(geneset_ids, thresholds))
        resolved_genes = sorted(
            {g.lower() for g in input_genes} | {str(row[0]).lower() for row in cursor.fetchall()}
        )
    else:
        resolved_genes = sorted({g.lower() for g in input_genes})

    # Unique per-call temp-table names so concurrent ABBA runs don't collide.
    suffix = uuid4().hex[:12]
    input_table = f"abba_input_genes_{suffix}"
    interest_table = f"abba_genes_of_interest_{suffix}"
    matching_table = f"abba_matching_genesets_{suffix}"
    result_table = f"abba_result_genes_{suffix}"

    for table in (input_table, interest_table, matching_table, result_table):
        run(q.drop_table(table))

    run(q.create_input_genes_table(input_table, resolved_genes, species_ids))
    run(
        q.create_genes_of_interest_table(
            interest_table, input_table, species_ids, include_homology=include_homology
        )
    )
    run(q.create_matching_genesets_table(matching_table, interest_table, user_id, thresholds))
    run(
        q.create_result_genes_table(
            result_table,
            matching_table,
            interest_table,
            tiers,
            species_ids,
            min_genes,
            thresholds,
        )
    )

    result = ABBAResult()

    run(q.count_available_genes())
    result.available_genes = cursor.fetchone()[0]
    run(q.count_available_genesets(tiers))
    result.available_genesets = cursor.fetchone()[0]

    run(q.select_genes_of_interest(interest_table))
    result.genes_of_interest = cursor.fetchall()
    run(q.select_input_species(interest_table))
    result.input_species = cursor.fetchall()

    # The matching-gene-set list uses the effective gene gate (0 under "auto").
    matching_gate = min_genes if min_genes is not None else 0
    run(q.select_matching_genesets(matching_table, tiers, matching_gate, result_limit))
    result.geneset_results = cursor.fetchall()

    run(q.select_result_genes(result_table, min_genesets, result_limit))
    result.gene_results = cursor.fetchall()

    run(q.select_max_occurrences(result_table))
    result.max_occurrences = cursor.fetchall()

    for gene_row in result.gene_results:
        ode_gene_id = gene_row[0]

        run(q.select_gene_ref_ids(ode_gene_id))
        result.ode_mapping[ode_gene_id] = [row[0] for row in cursor.fetchall()]
        run(q.select_preferred_ref_id(ode_gene_id))
        pref = cursor.fetchone()
        if pref:
            result.preferred_mapping[ode_gene_id] = pref[0]

        run(q.count_genesets_by_tier(ode_gene_id, thresholds))
        result.tier_counts[ode_gene_id] = {cur_id: count for count, cur_id in cursor.fetchall()}
        run(q.count_genesets_by_species(ode_gene_id, thresholds))
        result.species_counts[ode_gene_id] = {sp_id: count for count, sp_id in cursor.fetchall()}

    return result
