"""Endpoints related to system health."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from jax.apiutils import Response

from geneweaver.api import dependencies as deps
from geneweaver.api.services import monitors as monitors_service

from . import message as api_message

router = APIRouter(prefix="/monitors", tags=["monitors"])


@router.get("/servers/health")
def get_health_check(
    cursor: deps.Cursor | None = Depends(deps.cursor),
    db_health_check: Annotated[
        bool | None, Query(description=api_message.CHECK_DB_HEALTH)
    ] = False,
) -> Response:
    """Return 200 API response if reachable and optionally check db health."""
    response = {
        "status": "UP",
        "details": "All systems normal.",
        "datetime": datetime.utcnow(),
    }

    if db_health_check:
        db_health_response = monitors_service.check_db_health(cursor)
        response["DB_status"] = db_health_response

    return Response(response)
