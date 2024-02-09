from typing import Optional, Type
from sqlalchemy.orm import Session
from geneweaver.aon.models import Ortholog, Gene


def get_ortholog_id_gene(
        db: Session,
        ortholog_id: int) -> Optional[Type[Gene]]:
    """Get ortholog by id."""
    ortho = db.query(Ortholog).filter(Ortholog.ortholog_id == ortholog_id).first()
    return db.query(Gene).filter(Gene.gn_id == ortho.to_gene).first()
