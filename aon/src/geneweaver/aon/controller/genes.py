from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from geneweaver.aon import dependencies as deps
from geneweaver.aon.enum import ReferenceGeneIDType
from geneweaver.aon.service import convert as convert_service
from geneweaver.aon.service import genes as genes_service

router = APIRouter(prefix="/genes", tags=["genes"])


@router.get("")
def get_genes(
    species_id: Optional[int] = None,
    prefix: Optional[str] = None,
    paging_params: dict = Depends(deps.paging_parameters),
    db: deps.Session = Depends(deps.session),
):
    """Get all genes."""
    return genes_service.get_genes(
        db, species_id=species_id, prefix=prefix, **paging_params
    )


@router.get("/prefixes")
def get_gene_prefixes(db: deps.Session = Depends(deps.session)):
    """Get gene prefixes."""
    return genes_service.gene_prefixes(db)


@router.get("/{gene_id}")
def get_gene(gene_id: int, db: deps.Session = Depends(deps.session)):
    """Get gene by id."""
    return genes_service.gene_by_id(gene_id, db)


@router.get("/by-ref-id/{ref_id}")
def get_gene_by_ref_id(
    ref_id: str,
    ref_id_type: ReferenceGeneIDType = ReferenceGeneIDType.GW,
    db: deps.Session = Depends(deps.session),
):
    """Get gene by reference id."""
    if ref_id_type == ReferenceGeneType.AON_REF_ID:
        ref_id = convert_service.ode_ref_to_agr(db, ref_id)
    return genes_service.gene_by_ref_id(ref_id, db)


@router.get("/covert/{id}")
def covert_gene_id(
    id: str,
    from_type: ReferenceGeneIDType = ReferenceGeneIDType.AON,
    to_type: ReferenceGeneIDType = ReferenceGeneIDType.GW,
    geneweaver_id_type: Optional[ReferenceGeneIDType] = None,
    db: deps.Session = Depends(deps.session),
):
    """Convert gene id."""
    if from_type == ReferenceGeneIDType.GW and to_type == ReferenceGeneIDType.AON:
        return convert_service.ode_ref_to_agr(db, id)

    if from_type == ReferenceGeneIDType.AON and to_type == ReferenceGeneIDType.GW:
        return convert_service.agr_ref_to_ode(id)

    else:
        raise HTTPException(400, detail="Invalid gene id type conversion.")
