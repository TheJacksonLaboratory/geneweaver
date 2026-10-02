"""Filling in tool input that is too large to send through Temporal.

Most tools receive everything they need in the request. MSET does not: its two background
universes are the full gene space for a species, which is ~100,000 identifiers and measures
1.8-2.7 MiB once encoded -- at or over Temporal's 2 MiB message limit, and repeated into
workflow history on every run. That is what kept MSET off AsyncTask (G3-784).

A request instead carries a *reference* to the universe, and the resolver here expands it
inside the activity, against the database, just before the tool runs. The tools stay pure;
only this module and `db.py` know a database exists.

Resolvers are registered per tool rather than branched on inline, so the activity does not
need to know which tools have large inputs.
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from psycopg import Cursor

logger = logging.getLogger(__name__)

#: Key in the request envelope, alongside "tool" and "input".
UNIVERSE_KEY = "universe"


def _resolve_species(cursor: "Cursor", reference: dict) -> int:
    """Work out which species' gene space to return.

    Accepts the species directly, or the gene sets whose species to use -- the API and UI
    hold gene set ids, not species ids, and deriving it here keeps that lookup out of the
    submission path.

    :raises ValueError: If the reference is unusable, or the gene sets disagree on species.
    """
    from geneweaver.db.tool_input import species_by_geneset

    species_id = reference.get("species_id")
    if species_id is not None:
        if not isinstance(species_id, int) or isinstance(species_id, bool):
            raise ValueError(f"universe.species_id must be an integer; got {species_id!r}.")
        return species_id

    geneset_ids = reference.get("geneset_ids")
    if not geneset_ids:
        raise ValueError(
            "universe must give either 'species_id' or 'geneset_ids' to derive it from."
        )
    if not isinstance(geneset_ids, list) or not all(
        isinstance(gs_id, int) and not isinstance(gs_id, bool) for gs_id in geneset_ids
    ):
        raise ValueError(f"universe.geneset_ids must be a list of integers; got {geneset_ids!r}.")

    found = species_by_geneset(cursor, geneset_ids)
    missing = [gs_id for gs_id in geneset_ids if gs_id not in found]
    if missing:
        raise ValueError(f"No such gene set(s): {missing}.")

    species = set(found.values())
    if len(species) > 1:
        # Legacy refused this too: a shared background cannot represent two gene spaces.
        raise ValueError(
            "MSET cannot compare gene sets from different species "
            f"(found species {sorted(species)} across gene sets {sorted(found)})."
        )
    return species.pop()


def resolve_mset_input(cursor: "Cursor", tool_input: dict, reference: dict) -> dict:
    """Expand an MSET universe reference into both background lists.

    One universe serves both groups: the member lists are resolved as preferred gene
    symbols, so the background has to be the symbol space for the species, and MSET already
    requires both gene sets to be the same species. Legacy kept a separate background per
    group, keyed off each gene set's own identifier type -- which for any type other than
    Gene Symbol produced a background the members could not belong to.

    :raises ValueError: If the reference is unusable or the species has no genes.
    """
    from geneweaver.db.tool_input import gene_universe

    species_id = _resolve_species(cursor, reference)
    universe = gene_universe(cursor, species_id)
    if not universe:
        raise ValueError(
            f"No genes found for species {species_id}, so MSET has no background to sample "
            "from. Check the species id."
        )
    logger.info("Resolved MSET universe: species=%s genes=%d", species_id, len(universe))

    # An explicit list in the request wins, so a caller that has already resolved the
    # universe -- the API running in-process, or a test -- is not overridden.
    resolved = dict(tool_input)
    resolved.setdefault("group_1_background", universe)
    resolved.setdefault("group_2_background", universe)
    return resolved


#: Tool name -> resolver. A tool absent from this map needs no resolution.
INPUT_RESOLVERS: dict[str, Callable[["Cursor", dict, dict], dict]] = {
    "mset": resolve_mset_input,
}


def needs_resolution(tool: str, request: dict) -> bool:
    """Whether this request asks for input to be resolved from the database."""
    return tool in INPUT_RESOLVERS and bool(request.get(UNIVERSE_KEY))


def resolve_input(tool: str, request: dict) -> dict[str, Any]:
    """Return the tool input for `request`, expanding any reference it carries.

    Opens a database connection only when there is something to resolve, so tools that need
    no database keep running in a worker with no database settings.

    :raises ValueError: If the reference is unusable.
    :raises DatabaseNotConfigured: If resolution is needed but the worker cannot connect.
    """
    tool_input = request.get("input") or {}
    if not needs_resolution(tool, request):
        return dict(tool_input)

    from geneweaver.tools.temporal.db import cursor as db_cursor

    with db_cursor() as cursor:
        return INPUT_RESOLVERS[tool](cursor, tool_input, request[UNIVERSE_KEY])
