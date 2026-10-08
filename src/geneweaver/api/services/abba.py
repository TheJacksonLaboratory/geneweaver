"""ABBA, legacy's gene-centred search, run against the database.

ABBA is not one of the `geneweaver.tools` analyses: it is a SQL pipeline over the whole
gene-set corpus (`geneweaver.db.abba`), so there is nothing to ship to AsyncTask without
also shipping the database. It runs here, on a pooled connection, for as long as the
search takes -- 20 to 60 seconds on dev, as legacy's Celery task did. Three things keep
that from hurting other requests:

- at most `ABBA_MAX_CONCURRENT` searches run at once per process; the next is refused
  with `ABBABusy` (503) instead of queueing on the pool;
- each query is bounded by `ABBA_STATEMENT_TIMEOUT_SECONDS`, set for the search's own
  transaction only;
- the pipeline's temp tables drop when that transaction ends, so the connection goes back
  to the pool clean.
"""

import threading
from collections.abc import Callable
from contextlib import AbstractContextManager

from geneweaver.db.abba import ABBAResult as PipelineResult
from geneweaver.db.abba import abba
from psycopg import Cursor
from psycopg.rows import tuple_row

from geneweaver.api.core.config import settings
from geneweaver.api.schemas.auth import User
from geneweaver.api.schemas.tools import ABBARequest, ABBAResult
from geneweaver.api.services.geneset import determine_user_id
from geneweaver.api.services.tools import _gate_geneset_access, _require_user

#: Legacy's ABBA result page lists the top 50 gene sets and genes.
RESULT_LIMIT = 50

_running = threading.BoundedSemaphore(settings.ABBA_MAX_CONCURRENT)


class ABBABusy(Exception):
    """Too many searches are running in this process; the caller should retry (503)."""


def run_abba(
    open_cursor: Callable[[], AbstractContextManager[Cursor]],
    request: ABBARequest,
    user: User | None,
) -> ABBAResult:
    """Gate, run and shape one ABBA search.

    :raises SignInRequired: If the caller is anonymous.
    :raises ABBABusy: If `ABBA_MAX_CONCURRENT` searches are already running.
    :raises UnauthorizedException: If a seed gene set is not readable by the caller.
    """
    # Before the semaphore and the cursor: an anonymous request is refused for free.
    _require_user(user)
    if not _running.acquire(blocking=False):
        raise ABBABusy(
            f"{settings.ABBA_MAX_CONCURRENT} ABBA searches are already running; "
            "try again in a minute."
        )
    try:
        with open_cursor() as cursor:
            _gate_geneset_access(cursor, user, request.geneset_ids)
            return search(cursor, request, determine_user_id(user))
    finally:
        _running.release()


def search(cursor: Cursor, request: ABBARequest, user_id: int) -> ABBAResult:
    """Run the pipeline in its own transaction and shape the result.

    The transaction scopes both the statement timeout (`set_config(..., true)` is
    `SET LOCAL`) and the pipeline's `ON COMMIT DROP` temp tables. The pipeline reads rows by
    position, so it gets a tuple-row cursor on the same connection: the pool's are
    dict-row.
    """
    connection = cursor.connection
    with connection.transaction(), connection.cursor(row_factory=tuple_row) as rows:
        rows.execute(
            "SELECT set_config('statement_timeout', %s, true)",
            (f"{settings.ABBA_STATEMENT_TIMEOUT_SECONDS}s",),
        )
        species = _names(rows, "SELECT sp_id, sp_name FROM odestatic.species ORDER BY sp_id")
        tiers = _names(rows, "SELECT cur_id, cur_name FROM odestatic.curation_levels")
        attributions = _names(rows, "SELECT at_id, at_abbrev FROM odestatic.attribution")
        found = abba(
            rows,
            request.genes,
            geneset_ids=request.geneset_ids,
            # Unrestricted means every species, as legacy's form did.
            species_ids=request.species_ids or list(species),
            tiers=request.tiers,
            user_id=user_id,
            include_homology=request.include_homology,
            min_genes=request.min_genes,
            # Legacy's "Auto" is no floor.
            min_genesets=request.min_genesets or 0,
            result_limit=RESULT_LIMIT,
        )
    return shape(found, request, species, tiers, attributions)


def _names(cursor: Cursor, query: str) -> dict[int, str]:
    cursor.execute(query)
    return dict(cursor.fetchall())


def shape(
    found: PipelineResult,
    request: ABBARequest,
    species: dict[int, str],
    tiers: dict[int, str],
    attributions: dict[int, str | None],
) -> ABBAResult:
    """Name the pipeline's positional rows; the UI renders from these fields."""
    species_ids = {name: key for key, name in species.items()}
    return ABBAResult(
        parameters=request.model_dump(exclude={"genes", "geneset_ids"}),
        available_genes=found.available_genes,
        available_genesets=found.available_genesets,
        input_species=sorted(name for (name,) in found.input_species),
        seed_genes=[
            {
                "ode_gene_id": gene_id,
                "symbol": symbol,
                "species_id": species_ids.get(species_name),
                "species": species_name,
            }
            for gene_id, symbol, species_name in found.genes_of_interest
        ],
        genesets=[
            {
                "gs_id": gs_id,
                "name": name,
                "abbreviation": abbreviation,
                "description": description,
                "matches": matches,
                "tier": tier,
                "species_id": species_id,
                # Attribution 1 is the placeholder "none" (abbreviation NULL).
                "attribution": attributions.get(attribution) if attribution else None,
                "gene_count": gene_count,
            }
            for (
                gs_id,
                name,
                matches,
                tier,
                species_id,
                attribution,
                abbreviation,
                description,
                gene_count,
            ) in found.geneset_results
        ],
        genes=[
            {
                "ode_gene_id": gene_id,
                # The row's own ref id is whichever identifier the join met first (an
                # Ensembl or HGNC id as often as a symbol); the preferred symbol is the name.
                "symbol": found.preferred_mapping.get(gene_id)
                or next(iter(found.ode_mapping.get(gene_id, [])), ref_id),
                "symbols": found.ode_mapping.get(gene_id, []),
                "species_id": species_id,
                "species": species_name,
                "occurrences": occurrences,
                "tier_counts": found.tier_counts.get(gene_id, {}),
                "species_counts": found.species_counts.get(gene_id, {}),
            }
            for gene_id, ref_id, species_name, species_id, occurrences in found.gene_results
        ],
        max_occurrences=found.max_occurrences[0][0] if found.max_occurrences else 0,
        species={key: name for key, name in species.items() if name},
        tiers=tiers,
    )
