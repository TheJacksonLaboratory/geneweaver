"""API endpoints for the getting data load versions."""

from fastapi import APIRouter, Depends, Request
from geneweaver.aon import dependencies as deps
from geneweaver.aon.models import Version

router = APIRouter(prefix="/versions", tags=["versions"])


@router.get("/")
def get_versions(
    db: deps.Session = Depends(deps.session),
):
    """Get all versions.

    A version is a specific data load in the database. This endpoint returns
    all versions in the database that are currently available.
    """
    return db.query(Version).filter(Version.load_complete == True).all()  # noqa: E712


@router.get("/default")
def current_default_version(
    request: Request,
    db: deps.Session = Depends(deps.session),
):
    """Get the default schema version ID.

    This endpoint returns the default schema version ID. This is the version
    of the schema that the API will use if no version is specified.
    """
    return request.app.default_schema_version_id
