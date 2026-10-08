"""Running ABBA against the database and naming what it finds.

Unlike the other tools, ABBA is not a computation over input it is handed: it is a SQL
pipeline over the whole gene-set corpus (`geneweaver.db.abba`). So it takes a connection,
which is why it lives outside the `geneweaver.tools` registry and its `AbstractTool`
contract, and needs the `db` extra. The Temporal activity runs it on the tool worker; the
API runs the same function in-process where AsyncTask is not configured.
"""

from typing import TYPE_CHECKING

from geneweaver.tools.abba.schema import ABBAInput, ABBAOutput

if TYPE_CHECKING:  # pragma: no cover - typing only
    from geneweaver.db.abba import ABBAResult as PipelineResult
    from psycopg import Connection, Cursor

#: Legacy's ABBA result page lists the top 50 gene sets and genes.
RESULT_LIMIT = 50

#: Bounds each of the pipeline's queries. Its slowest step takes ~14 s on dev.
DEFAULT_STATEMENT_TIMEOUT_SECONDS = 240


def search(
    connection: "Connection",
    request: ABBAInput,
    user_id: int,
    statement_timeout_seconds: int = DEFAULT_STATEMENT_TIMEOUT_SECONDS,
) -> ABBAOutput:
    """Run the pipeline in its own transaction and shape the result.

    The transaction scopes both the statement timeout (`set_config(..., true)` is
    `SET LOCAL`) and the pipeline's `ON COMMIT DROP` temp tables, so the connection is left
    clean. The pipeline reads rows by position, so it runs on a tuple-row cursor whatever
    the connection's default row factory.

    :param user_id: Whose private gene sets may match; 0 for public gene sets only.
    """
    from geneweaver.db.abba import abba
    from psycopg.rows import tuple_row

    with connection.transaction(), connection.cursor(row_factory=tuple_row) as rows:
        rows.execute(
            "SELECT set_config('statement_timeout', %s, true)",
            (f"{statement_timeout_seconds}s",),
        )
        species = _names(rows, "SELECT sp_id, sp_name FROM odestatic.species ORDER BY sp_id")
        tiers = _names(rows, "SELECT cur_id, cur_name FROM odestatic.curation_levels")
        attributions = _names(rows, "SELECT at_id, at_abbrev FROM odestatic.attribution")
        found = abba(
            rows,
            request.genes,
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


def _names(cursor: "Cursor", query: str) -> dict[int, str]:
    cursor.execute(query)
    return dict(cursor.fetchall())


def shape(
    found: "PipelineResult",
    request: ABBAInput,
    species: dict[int, str],
    tiers: dict[int, str],
    attributions: dict[int, str | None],
) -> ABBAOutput:
    """Name the pipeline's positional rows; the UI renders from these fields."""
    species_ids = {name: key for key, name in species.items()}
    return ABBAOutput(
        parameters=request.model_dump(exclude={"genes"}),
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
