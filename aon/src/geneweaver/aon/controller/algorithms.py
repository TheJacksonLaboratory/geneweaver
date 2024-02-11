from fastapi import APIRouter, Depends
from typing import Optional
from geneweaver.aon import dependencies as deps
from geneweaver.aon.service import algorithms as algorithms_service

router = APIRouter(prefix="/algorithms", tags=["algorithms"])


@router.get("")
def get_algorithms(
    name: Optional[str] = None, db: deps.Session = Depends(deps.session)
):
    """Get all algorithms."""
    if name is not None:
        return algorithms_service.algorithm_by_name(name, db)

    return algorithms_service.all_algorithms(db)


@router.get("/{algorithm_id}")
def get_algorithm(algorithm_id: int, db: deps.Session = Depends(deps.session)):
    """Get algorithm by id."""
    return algorithms_service.algorithm_by_id(algorithm_id, db)
