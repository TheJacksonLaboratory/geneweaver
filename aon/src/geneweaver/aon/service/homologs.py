"""Module with functions for getting homologs from the database."""

from typing import List, Optional, Type

from geneweaver.aon.models import Homology
from geneweaver.aon.service.utils import apply_paging
from sqlalchemy.orm import Session


def get_homologs(
    db: Session,
    homolog_id: Optional[int] = None,
    source_name: Optional[str] = None,
    species_id: Optional[int] = None,
    gene_id: Optional[int] = None,
    start: Optional[int] = None,
    limit: Optional[int] = 1000,
) -> List[Type[Homology]]:
    """Get homologs with optional filters.

    :param db: The database session.
    :param homolog_id: The homolog ID.
    :param source_name: The source name.
    :param species_id: The species ID.
    :param gene_id: The gene ID.
    :param start: The start index for paging.
    :param limit: The number of results to return.
    :return: The homologs with optional filters.
    """
    base_query = db.query(Homology)
    if homolog_id is not None:
        base_query = base_query.filter(Homology.hom_id == homolog_id)
    if source_name is not None:
        base_query = base_query.filter(Homology.hom_source_name == source_name)
    if species_id is not None:
        base_query = base_query.filter(Homology.sp_id == species_id)
    if gene_id is not None:
        base_query = base_query.filter(Homology.gn_id == gene_id)
    base_query = apply_paging(base_query, start, limit)

    return base_query.all()


def homolog_sources(db: Session) -> List[str]:
    """Get all homolog sources.

    :param db: The database session.
    :return: All homolog sources.
    """
    results = db.query(Homology.hom_source_name).distinct().all()
    return [r.hom_source_name for r in results]
