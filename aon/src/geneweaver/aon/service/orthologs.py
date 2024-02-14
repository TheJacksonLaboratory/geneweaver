from typing import Optional, Type

from geneweaver.aon.models import Algorithm, Gene, Ortholog, OrthologAlgorithms
from geneweaver.aon.service.utils import apply_paging
from sqlalchemy.orm import Session, aliased


def get_ortholog_from_gene(db: Session, ortholog_id: int) -> Optional[Type[Gene]]:
    """Get ortholog by id."""
    ortholog = get_ortholog(db, ortholog_id)
    if ortholog is None:
        return None
    return db.query(Gene).get(get_ortholog(db, ortholog_id).from_gene)


def get_ortholog_to_gene(db: Session, ortholog_id: int) -> Optional[Type[Gene]]:
    """Get ortholog by id."""
    ortholog = get_ortholog(db, ortholog_id)
    if ortholog is None:
        return None
    return db.query(Gene).get(get_ortholog(db, ortholog_id).to_gene)


def get_orthologs(
    db: Session,
    from_species: Optional[int] = None,
    to_species: Optional[int] = None,
    from_gene_id: Optional[int] = None,
    to_gene_id: Optional[int] = None,
    algorithm_id: Optional[int] = None,
    possible_match_algorithms: Optional[int] = None,
    best: Optional[bool] = None,
    revised: Optional[bool] = None,
    start: Optional[int] = None,
    limit: Optional[int] = 1000,
):
    query = db.query(Ortholog)

    if algorithm_id is not None:
        query = (
            query.join(OrthologAlgorithms)
            .join(Algorithm)
            .filter(Algorithm.alg_id == algorithm_id)
        )

    if from_species is not None:
        FromGene = aliased(Gene)
        query = query.join(FromGene, Ortholog.from_gene == FromGene.gn_id).filter(
            FromGene.sp_id == from_species
        )

    if to_species is not None:
        ToGene = aliased(Gene)
        query = query.join(ToGene, Ortholog.to_gene == ToGene.gn_id).filter(
            ToGene.sp_id == to_species
        )

    if from_gene_id:
        query = query.filter(Ortholog.from_gene == from_gene_id)

    if to_gene_id:
        query = query.filter(Ortholog.to_gene == to_gene_id)

    if best is not None:
        query = query.filter(Ortholog.ort_is_best == best)

    if revised is not None:
        query = query.filter(Ortholog.ort_is_best_revised == revised)

    if possible_match_algorithms is not None:
        query = query.filter(
            Ortholog.ort_num_possible_match_algorithms == possible_match_algorithms
        )

    query = apply_paging(query, start, limit)

    return query.all()


def get_ortholog(db: Session, ortholog_id: int):
    return db.query(Ortholog).get(ortholog_id)
