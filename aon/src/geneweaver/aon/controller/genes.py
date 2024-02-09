from typing import Optional
from fastapi import APIRouter, Depends
from geneweaver.aon import dependencies as deps
from geneweaver.aon.service import genes as genes_service

router = APIRouter(prefix="/genes", tags=["genes"])


@router.get("")
def get_genes(species_id: Optional[int] = None,
              prefix: Optional[str] = None,
              db: deps.Session = Depends(deps.session)):
    """Get all genes."""
    return genes_service.get_genes(db, species_id=species_id, prefix=prefix)


@router.get("/{gene_id}")
def get_gene(gene_id: int, db: deps.Session = Depends(deps.session)):
    """Get gene by id."""
    return genes_service.gene_by_id(gene_id, db)


@router.get("/ref_ids/{ref_id}")
def get_gene_by_ref_id(ref_id: str, db: deps.Session = Depends(deps.session)):
    """Get gene by reference id."""
    return genes_service.gene_by_ref_id(ref_id, db)


@router.get("/prefixes")
def get_gene_prefixes(db: deps.Session = Depends(deps.session)):
    """Get gene prefixes."""
    return genes_service.gene_prefixes(db)
