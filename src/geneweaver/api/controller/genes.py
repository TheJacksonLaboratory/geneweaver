"""Endpoints related to genes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from geneweaver.core.enum import GeneIdentifier, Species
from geneweaver.core.schema.gene import Gene
from jax.apiutils import CollectionResponse, Response

from geneweaver.api import dependencies as deps
from geneweaver.api.schemas.apimodels import (
    GeneIdHomologReq,
    GeneIdMappingAonReq,
    GeneIdMappingReq,
    GeneIdMappingResp,
)
from geneweaver.api.services import genes as genes_service

from . import message as api_message

router = APIRouter(prefix="/genes", tags=["genes"])


@router.get("")
def get_genes(
    cursor: deps.Cursor | None = Depends(deps.cursor),
    reference_id: Annotated[str | None, Query(description=api_message.GENE_REFERENCE)] = None,
    gene_database: GeneIdentifier | None = None,
    species: Species | None = None,
    preferred: Annotated[bool | None, Query(description=api_message.GENE_PREFERRED)] = None,
    limit: Annotated[
        int | None,
        Query(
            format="int64",
            minimum=0,
            maxiumum=1000,
            description=api_message.LIMIT,
        ),
    ] = None,
    offset: Annotated[
        int | None,
        Query(
            format="int64",
            minimum=0,
            maxiumum=9223372036854775807,
            description=api_message.OFFSET,
        ),
    ] = None,
) -> CollectionResponse[Gene]:
    """Get geneweaver list of genes."""
    if limit is None:
        limit = 100

    response = genes_service.get_genes(
        cursor, reference_id, gene_database, species, preferred, limit, offset
    )
    return CollectionResponse[Gene](**response)


@router.get("/{gene_id}/preferred")
def get_gene_preferred(
    gene_id: Annotated[int, Path(format="int64", minimum=0, maxiumum=9223372036854775807)],
    cursor: deps.Cursor | None = Depends(deps.cursor),
) -> Response[Gene]:
    """Get preferred gene for a given gene ode_id."""
    response = genes_service.get_gene_preferred(cursor, gene_id)
    return Response[Gene](response)


@router.post("/homologs", response_model=GeneIdMappingResp, deprecated=True)
def get_related_gene_ids(
    gene_id_mapping: GeneIdHomologReq,
    cursor: deps.Cursor | None = Depends(deps.cursor),
) -> GeneIdMappingResp:
    """Get homologous gene ids given list of gene ids."""
    response = genes_service.get_homolog_ids(
        cursor,
        gene_id_mapping.source_ids,
        gene_id_mapping.target_gene_id_type,
        gene_id_mapping.source_gene_id_type,
        gene_id_mapping.target_species,
        gene_id_mapping.source_species,
    )

    resp_id_map = response.get("ids_map")
    gene_id_mapping_resp = GeneIdMappingResp(gene_ids_map=resp_id_map)

    return gene_id_mapping_resp


@router.post("/mappings", response_model=GeneIdMappingResp)
def get_genes_mapping(
    gene_id_mapping: GeneIdMappingReq,
    cursor: deps.Cursor | None = Depends(deps.cursor),
) -> GeneIdMappingResp:
    """Get gene ids mapping."""
    response = genes_service.get_gene_mapping(
        cursor,
        gene_id_mapping.source_ids,
        gene_id_mapping.species,
        gene_id_mapping.target_gene_id_type,
    )

    resp_id_map = response.get("ids_map")
    gene_id_mapping_resp = GeneIdMappingResp(gene_ids_map=resp_id_map)

    return gene_id_mapping_resp


@router.post("/mappings/aon", response_model=GeneIdMappingResp)
def get_genes_mapping_aon(
    gene_id_mapping: GeneIdMappingAonReq,
    cursor: deps.Cursor | None = Depends(deps.cursor),
) -> GeneIdMappingResp:
    """Get gene ids mapping given list of gene ids and target gene identifier type."""
    response = genes_service.get_gene_aon_mapping(
        cursor, gene_id_mapping.source_ids, gene_id_mapping.species
    )

    resp_id_map = response.get("ids_map")
    gene_id_mapping_resp = GeneIdMappingResp(gene_ids_map=resp_id_map)

    return gene_id_mapping_resp
