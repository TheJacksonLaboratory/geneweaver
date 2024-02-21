"""Service code for interacting with the Algorithm table."""

from typing import List, Type

from geneweaver.aon.models import Algorithm
from sqlalchemy.orm import Session


def all_algorithms(db: Session) -> List[Type[Algorithm]]:
    """Get all algorithms.

    :param db: The database session.
    :return: All algorithms.
    """
    return db.query(Algorithm).all()


def algorithm_by_id(db: Session, algorithm_id: int) -> Type[Algorithm]:
    """Get algorithm by ID.

    :param db: The database session.
    :param algorithm_id: The algorithm ID.
    :return: The algorithm with the provided ID.
    """
    return db.query(Algorithm).get(algorithm_id)


def algorithm_by_name(db: Session, algorithm_name: str) -> List[Type[Algorithm]]:
    """Get algorithm by name.

    :param algorithm_name: The algorithm name.
    :param db: The database session.
    :return: The algorithm with the provided name.
    """
    return db.query(Algorithm).filter(Algorithm.alg_name == algorithm_name).all()
