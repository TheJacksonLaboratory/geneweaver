"""Search genesets using all relevant metadata fields."""

from datetime import date

from geneweaver.db.query import search
from geneweaver.db.utils import (
    GenesetScoreTypeOrScoreTypes,
    GenesetTierOrTiers,
    SpeciesOrSpeciesSet,
)
from psycopg import Cursor
from psycopg.rows import Row


def genesets(
    cursor: Cursor,
    search_text: str,
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
    limit: int | None = None,
    offset: int | None = None,
    _status: str | None = "normal",
) -> list[Row]:
    """Search genesets using all relevant metadata fields.

    :param cursor: A database cursor.
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
    """
    cursor.execute(
        *search.genesets(
            search_text,
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
            limit=limit,
            offset=offset,
            _status=_status,
        )
    )
    return cursor.fetchall()
