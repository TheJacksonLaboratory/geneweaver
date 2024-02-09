from geneweaver.aon.models import Algorithm
from sqlalchemy.orm import Session


def all_algorithms(db: Session):
    return db.query(Algorithm).all()


def algorithm_by_id(algorithm_id: int, db: Session):
    return db.query(Algorithm).get(algorithm_id)


def algorithm_by_name(algorithm_name: str, db: Session):
    return db.query(Algorithm).filter(Algorithm.alg_name == algorithm_name).all()
