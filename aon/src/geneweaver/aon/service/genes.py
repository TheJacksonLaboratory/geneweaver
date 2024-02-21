"""Module with database functions for genes."""
from typing import List, Optional, Type

from geneweaver.aon.models import Gene
from geneweaver.aon.service.utils import apply_paging
from sqlalchemy.orm import Session


def get_genes(
    db: Session,
    species_id: Optional[int] = None,
    prefix: Optional[str] = None,
    start: Optional[int] = None,
    limit: Optional[int] = 1000,
) -> List[Type[Gene]]:
    """Get all genes with optional filtering.

    :param db: The database session.
    :param species_id: The species id to filter by.
    :param prefix: The gene prefix to filter by.
    :param start: The start index for paging.
    :param limit: The limit for paging.
    :return: All genes with optional filtering.
    """
    query = db.query(Gene)
    if species_id is not None:
        query = query.filter(Gene.sp_id == species_id)
    if prefix is not None:
        query = query.filter(Gene.gn_prefix == prefix)
    query = apply_paging(query, start, limit)
    return query.all()


def gene_by_id(db: Session, gene_id: int) -> Type[Gene]:
    """Get a gene by id.

    :param db: The database session.
    :param gene_id: The gene id to search for.
    :return: The gene with the id.
    """
    return db.query(Gene).get(gene_id)


def gene_by_ref_id(db: Session, ref_id: str) -> List[Type[Gene]]:
    """Get a gene by reference id.

    :param db: The database session.
    :param ref_id: The reference id to search for.
    :return: The gene with the reference id.
    """
    return db.query(Gene).filter(Gene.gn_ref_id == ref_id).all()


def genes_by_prefix(db: Session, prefix: str) -> List[Type[Gene]]:
    """Get all genes by prefix.

    :param db: The database session.
    :param prefix: The gene prefix to search for.
    :return: All genes with the prefix.
    """
    return db.query(Gene).filter(Gene.gn_prefix == prefix).all()


def gene_prefixes(db: Session) -> List[str]:
    """Get all gene prefixes.

    :param db: The database session.
    :return: All gene prefixes.
    """
    results = db.query(Gene).distinct(Gene.gn_prefix).all()
    return [r.gn_prefix for r in results]


def genes_by_species_id(db: Session, species_id: int) -> List[Type[Gene]]:
    """Get all genes for a species.

    :param db: The database session.
    :param species_id: The species id to search for.
    :return: All genes for the species.
    """
    return db.query(Gene).filter(Gene.sp_id == species_id).all()
