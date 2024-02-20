from typing import Optional

from fastapi import APIRouter, Depends, Request
from geneweaver.aon import dependencies as deps
from geneweaver.aon.models import Version

router = APIRouter(prefix="/versions", tags=["versions"])


@router.get("/")
def get_versions(
    db: deps.Session = Depends(deps.session),
):
    return db.query(Version).all()


@router.get("/default")
def current_default_version(
    request: Request,
    db: deps.Session = Depends(deps.session),
):
    return request.app.default_schema_version_id
