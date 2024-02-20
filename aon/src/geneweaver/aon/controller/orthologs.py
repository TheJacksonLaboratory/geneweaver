from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from geneweaver.aon import dependencies as deps
from geneweaver.aon.service import orthologs as orthologs_service

router = APIRouter(prefix="/orthologs", tags=["orthologs"])


@router.get("/")
def get_orthologs(
    from_species: Optional[int] = None,
    to_species: Optional[int] = None,
    from_gene_id: Optional[int] = None,
    to_gene_id: Optional[int] = None,
    algorithm_id: Optional[int] = deps.DEFAULT_ALGORITHM_ID,
    best: Optional[bool] = None,
    revised: Optional[bool] = None,
    paging_params: dict = Depends(deps.paging_parameters),
    db: deps.Session = Depends(deps.session),
):
    """Get ortholog by id."""
    return orthologs_service.get_orthologs(
        db,
        from_species=from_species,
        to_species=to_species,
        from_gene_id=from_gene_id,
        to_gene_id=to_gene_id,
        algorithm_id=algorithm_id,
        best=best,
        revised=revised,
        **paging_params,
    )


@router.get("/{ortholog_id}")
def get_orthologs_by_id(
    ortholog_id: int,
    source_name: Optional[str] = None,
    species_id: Optional[int] = None,
    gene_id: Optional[int] = None,
    db: deps.Session = Depends(deps.session),
):
    """Get ortholog by id."""
    return orthologs_service.get_ortholog(db, ortholog_id)


@router.get("/{ortholog_id}/from_gene")
def get_ortholog_id_gene(ortholog_id: int, db: deps.Session = Depends(deps.session)):
    """Get ortholog by id."""
    orthologs = orthologs_service.get_ortholog_from_gene(db, ortholog_id)
    if not orthologs:
        raise HTTPException(404, detail="Could not find any genes.")
    return orthologs


@router.get("/{ortholog_id}/to_gene")
def get_ortholog_id_gene(ortholog_id: int, db: deps.Session = Depends(deps.session)):
    """Get ortholog by id."""
    orthologs = orthologs_service.get_ortholog_to_gene(db, ortholog_id)
    if not orthologs:
        raise HTTPException(404, detail="Could not find any genes.")
    return orthologs
