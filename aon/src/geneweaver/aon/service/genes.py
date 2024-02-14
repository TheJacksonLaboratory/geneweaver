from typing import Optional

from geneweaver.aon.models import Gene
from geneweaver.aon.service.utils import apply_paging
from sqlalchemy.orm import Session


def get_genes(
    db: Session,
    species_id: Optional[int] = None,
    prefix: Optional[str] = None,
    start: Optional[int] = None,
    limit: Optional[int] = 1000,
):
    query = db.query(Gene)
    if species_id is not None:
        query = query.filter(Gene.sp_id == species_id)
    if prefix is not None:
        query = query.filter(Gene.gn_prefix == prefix)
    query = apply_paging(query, start, limit)
    return query.all()


def gene_by_id(gene_id: int, db: Session):
    return db.query(Gene).get(gene_id)


def gene_by_ref_id(ref_id: str, db: Session):
    return db.query(Gene).filter(Gene.gn_ref_id == ref_id).all()


def genes_by_prefix(prefix: str, db: Session):
    return db.query(Gene).filter(Gene.gn_prefix == prefix).all()


def gene_prefixes(db: Session):
    results = db.query(Gene).distinct(Gene.gn_prefix).all()
    return [r.gn_prefix for r in results]


def genes_by_species_id(db: Session, species_id):
    return db.query(Gene).filter(Gene.sp_id == species_id).all()
