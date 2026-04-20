"""SQL query generation code for reading genesets."""

from datetime import date

from geneweaver.core.enum import GeneIdentifier, Species
from geneweaver.db.query.geneset.const import GENESET_TSVECTOR
from geneweaver.db.query.geneset.utils import (
    add_ontology_parameter,
    add_ontology_query,
    format_select_query,
    is_readable,
    restrict_score_type,
    restrict_tier,
)
from geneweaver.db.query.search.utils import search
from geneweaver.db.query.utils import (
    add_op_filters,
    construct_filters,
)
from geneweaver.db.utils import (
    GenesetScoreTypeOrScoreTypes,
    GenesetTierOrTiers,
    limit_and_offset,
)
from psycopg.sql import SQL, Composed


def get(
    gs_id: int | None = None,
    owner_id: int | None = None,
    curation_tier: GenesetTierOrTiers | None = None,
    species: Species | None = None,
    name: str | None = None,
    abbreviation: str | None = None,
    publication_id: int | None = None,
    pubmed_id: int | None = None,
    gene_id_type: GeneIdentifier | None = None,
    search_text: str | None = None,
    status: str | None = "normal",
    limit: int | None = None,
    offset: int | None = None,
    is_readable_by: int | None = None,
    with_publication_info: bool = True,
    ontology_term: str | None = None,
    score_type: GenesetScoreTypeOrScoreTypes | None = None,
    lte_count: int | None = None,
    gte_count: int | None = None,
    created_after: date | None = None,
    created_before: date | None = None,
    updated_after: date | None = None,
    updated_before: date | None = None,
) -> tuple[Composed, dict]:
    """Get genesets.

    :param gs_id: Show only results with this geneset ID.
    :param owner_id: Show only results owned by this user ID.
    :param curation_tier: Show only results of this curation tier.
    :param species: Show only results associated with this species.
    :param name: Show only results with this name.
    :param abbreviation: Show only results with this abbreviation.
    :param publication_id: Show only results with this publication ID (internal).
    :param pubmed_id: Show only results with this PubMed ID.
    :param gene_id_type: Show only results with this gene ID type.
    :param search_text: Return genesets that match this search text (using PostgreSQL
                        full-text search).
    :param status: Show only results with this status. Default is "normal".
    :param limit: Limit the number of results.
    :param offset: Offset the results.
    :param is_readable_by: A user ID to check if the user can read the results.
    :param with_publication_info: Include publication info in the return.
    :param ontology_term: Show only results associated with this ontology term.
    :param score_type: Show only results with given score type.
    :param lte_count: less than or equal count.
    :param gte_count: greater than or equal count.
    :param updated_before: Show only results updated before this date.
    :param updated_after: Show only results updated after this date.
    :param created_before: Show only results created before this date.
    :param created_after: Show only results updated before this date.
    """
    params = {}
    filtering = []
    query = format_select_query(
        with_publication_info=with_publication_info,
        with_publication_join=pubmed_id is not None,
    )

    # expand query to include ontology term if needed
    if ontology_term:
        query = add_ontology_query(query=query)
        filtering, params = add_ontology_parameter(
            existing_filters=filtering,
            existing_params=params,
            ontology_term=ontology_term,
        )

    filtering, params = is_readable(filtering, params, is_readable_by)
    filtering, params = search(filtering, params, GENESET_TSVECTOR, search_text)
    filtering, params = restrict_tier(filtering, params, curation_tier)
    filtering, params = restrict_score_type(filtering, params, score_type)

    filtering, params = construct_filters(
        filtering,
        params,
        {
            "gs_id": gs_id,
            "usr_id": owner_id,
            "sp_id": int(species) if species is not None else None,
            "gs_name": name,
            "gs_abbreviation": abbreviation,
            "pub_id": publication_id,
            "pub_pubmed": str(pubmed_id) if pubmed_id is not None else None,
            "gs_gene_id_type": int(gene_id_type) if gene_id_type is not None else None,
            "gs_status": status,
        },
    )
    filtering, params = add_op_filters(
        filtering,
        params,
        lte_count=lte_count,
        gte_count=gte_count,
        created_before=created_before,
        created_after=created_after,
        updated_before=updated_before,
        updated_after=updated_after,
    )

    if len(filtering) > 0:
        query += SQL("WHERE") + SQL("AND").join(filtering)

    query = limit_and_offset(query, limit, offset).join(" ")

    return query, params


def shared_with_user(
    user_id: int,
    limit: int | None = None,
    offset: int | None = None,
    with_publication_info: bool = True,
) -> tuple[Composed, dict]:
    """Get Genesets that are shared with a user.

    NOTE: NOT IMPLEMENTED
    """
    raise NotImplementedError()


def by_project_id(
    project_id: int,
    limit: int | None = None,
    offset: int | None = None,
    is_readable_by: int | None = None,
    with_publication_info: bool = True,
) -> tuple[Composed, dict]:
    """Create a psycopg query to get genesets by project ID.

    :param project_id: The project ID to search for.
    :param limit: The limit of results to return.
    :param offset: The offset of results to return.
    :param is_readable_by: A user ID to check if the user can read the results.
    :param with_publication_info: Include publication info in the return.

    :return: A query (and params) that can be executed on a cursor.
    """
    query = (
        format_select_query(with_publication_info=with_publication_info)
        + SQL("JOIN project_geneset ON geneset.gs_id = project_geneset.gs_id")
        + SQL("INNER JOIN production.project2geneset")
        + SQL("ON geneset.gs_id=project2geneset.gs_id")
        + SQL("WHERE project2geneset.pj_id=%(project_id)s")
    )
    params = {"project_id": project_id}
    filtering, params = is_readable([], params, is_readable_by)

    if len(filtering) > 0:
        query += SQL("WHERE") + SQL("AND").join(filtering)
    query = limit_and_offset(query, limit, offset).join(" ")

    return query, params
