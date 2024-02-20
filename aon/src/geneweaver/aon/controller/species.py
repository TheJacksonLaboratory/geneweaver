from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from geneweaver.aon import dependencies as deps
from geneweaver.aon.service import genes as genes_service
from geneweaver.aon.service import homologs as homologs_service
from geneweaver.aon.service import species as species_service

router = APIRouter(prefix="/species", tags=["species"])


@router.get("")
def get_species(name: Optional[str] = None, db: deps.Session = Depends(deps.session)):
    """Get all species."""
    return species_service.get_species(db, name=name)


@router.get("/{species_id}")
def get_species(species_id: int, db: deps.Session = Depends(deps.session)):
    """Get species by id."""
    return species_service.species_by_id(db, species_id)


@router.get("/by-taxon-id/{taxon_id}")
def get_species_by_taxon_id(taxon_id: int, db: deps.Session = Depends(deps.session)):
    """Get species by taxon id."""
    return species_service.species_by_taxon_id(db, taxon_id)


@router.get("/{species_id}/geneweaver_id")
def get_geneweaver_id(species_id: int, db: deps.Session = Depends(deps.session)):
    """Get the GeneWeaver ID for a species."""
    return species_service.convert_species_agr_to_ode(db, species_id)


@router.get("/{species_id}/genes")
def get_species_genes(
    species_id: int,
    paging: dict = Depends(deps.paging_parameters),
    db: deps.Session = Depends(deps.session),
):
    """Get genes for a species."""
    genes = genes_service.get_genes(db, species_id=species_id, **paging)
    if not genes:
        raise HTTPException(404, detail="Could not find any genes with that species")
    return genes


@router.get("/{species_id}/homologs")
def get_species_homology(
    species_id: int,
    paging: dict = Depends(deps.paging_parameters),
    db: deps.Session = Depends(deps.session),
):
    """Get homology for a species."""
    homologs = homologs_service.get_homologs(db, species_id=species_id, **paging)
    if not homologs:
        raise HTTPException(404, detail="Could not find any homologs with that species")
    else:
        return homologs
