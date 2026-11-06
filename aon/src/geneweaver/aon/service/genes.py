"""Module with database functions for genes."""

from typing import List, Optional, Type

from geneweaver.aon.models import Gene, Homology, Ortholog, OrthologAlgorithms
from geneweaver.aon.service.utils import apply_paging
from sqlalchemy.orm import Session, aliased


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


def map_gene_orthologs(
    db: Session,
    gene_ref_ids: List[str],
    to_species: Optional[int] = None,
    algorithm_id: Optional[int] = None,
    start: Optional[int] = None,
    limit: Optional[int] = 1000,
) -> list:
    """Map gene orthologs.

    :param db: The database session.
    :param gene_ref_ids: The gene reference ids to map.
    :return: The mapped gene orthologs.
    """
    from_gene = aliased(Gene)
    to_gene = aliased(Gene)
    query = (
        db.query(from_gene, to_gene, Ortholog, OrthologAlgorithms)
        .join(Ortholog, Ortholog.from_gene == from_gene.gn_id)
        .join(to_gene, Ortholog.to_gene == to_gene.gn_id)
        .join(OrthologAlgorithms, Ortholog.ort_id == OrthologAlgorithms.ort_id)
        .filter(from_gene.gn_ref_id.in_(gene_ref_ids))
    )

    if to_species is not None:
        query = query.filter(to_gene.sp_id == to_species)

    if algorithm_id is not None:
        query = query.filter(OrthologAlgorithms.alg_id == algorithm_id)

    query = apply_paging(query, start, limit)

    results = query.all()

    return [
        {
            "from_gene": r[0].gn_ref_id,
            "to_gene": r[1].gn_ref_id,
            "ortholog_id": r[2].ort_id,
            "algorithm_id": r[3].alg_id,
        }
        for r in results
    ]


def map_gene_homologs(
    db: Session,
    gene_ref_ids: List[str],
    to_species: Optional[int] = None,
    start: Optional[int] = None,
    limit: Optional[int] = 1000,
) -> list:
    """Map gene homologs.

    :param db: The database session.
    :param gene_ref_ids: The gene reference ids to map.
    :return: The mapped gene homologs.
    """
    from_hom = aliased(Homology)
    to_hom = aliased(Homology)
    from_gene = aliased(Gene)
    to_gene = aliased(Gene)
    query = (
        db.query(from_gene, from_hom, to_hom, to_gene)
        .join(from_hom, from_gene.gn_id == from_hom.gn_id)
        .join(to_hom, from_hom.hom_id == to_hom.hom_id)
        .join(to_gene, to_hom.gn_id == to_gene.gn_id)
        .filter(from_gene.gn_ref_id.in_(gene_ref_ids))
    )

    if to_species is not None:
        query = query.filter(to_gene.sp_id == to_species)

    query = apply_paging(query, start, limit)

    results = query.all()

    return [
        {
            "from_gene": r[0].gn_ref_id,
            "to_gene": r[3].gn_ref_id,
            "homolog_id": r[1].hom_id,
        }
        for r in results
    ]


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
