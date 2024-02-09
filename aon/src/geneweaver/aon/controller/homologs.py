from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from geneweaver.aon import dependencies as deps
from geneweaver.aon.service import homologs as homologs_service

router = APIRouter(prefix="/homologs", tags=["homologs"])


@router.get("/")
def get_homologs(
        source_name: Optional[str] = None,
        species_id: Optional[int] = None,
        gene_id: Optional[int] = None,
        db: deps.Session = Depends(deps.session)):
    """Get homolog by id."""
    homologs = homologs_service.get_homologs(
        db,
        source_name=source_name,
        species_id=species_id,
        gene_id=gene_id
    )

    if not homologs:
        raise HTTPException(404, detail="Could not find any homologs")

    return homologs


@router.get("/sources")
def get_homolog_sources(db: deps.Session = Depends(deps.session)):
    """Get homolog sources."""
    return homologs_service.homolog_sources(db)


@router.get("/{homolog_id}")
def get_homologs_with_holog_id(
        homolog_id: int,
        source_name: Optional[str] = None,
        species_id: Optional[int] = None,
        gene_id: Optional[int] = None,
        db: deps.Session = Depends(deps.session)):
    """Get homolog by id."""

    homologs = homologs_service.get_homologs(
        db,
        homolog_id=homolog_id,
        source_name=source_name,
        species_id=species_id,
        gene_id=gene_id
    )

    if not homologs:
        raise HTTPException(404, detail="Could not find any homologs")

    return homologs
