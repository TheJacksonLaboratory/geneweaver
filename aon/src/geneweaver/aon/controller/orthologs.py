from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from geneweaver.aon import dependencies as deps
from geneweaver.aon.service import orthologs as orthologs_service
from geneweaver.aon.models import Species, Geneweaver_Species, Gene, Homology

router = APIRouter(prefix="/orthologs", tags=["orthologs"])


@router.get("/")
def get_orthologs(
        source_name: Optional[str] = None,
        species_id: Optional[int] = None,
        gene_id: Optional[int] = None,
        db: deps.Session = Depends(deps.session)):
    """Get ortholog by id."""



@router.get("/{ortholog_id}")
def get_orthologs_by_id(
        ortholog_id: int,
        source_name: Optional[str] = None,
        species_id: Optional[int] = None,
        gene_id: Optional[int] = None,
        db: deps.Session = Depends(deps.session)):
    """Get ortholog by id."""



@router.get("/{ortholog_id}/gene")
def get_ortholog_id_gene(
        ortholog_id: int,
        db: deps.Session = Depends(deps.session)):
    """Get ortholog by id."""
    orthologs = orthologs_service.get_ortholog_id_gene(db, ortholog_id)
    if not orthologs:
        raise HTTPException(404, detail="Could not find any genes.")
    return orthologs
