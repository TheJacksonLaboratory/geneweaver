"""Dependency injection for the AON FastAPI application."""

import logging
from contextlib import asynccontextmanager
from typing import Annotated, Optional, Union

from fastapi import FastAPI, HTTPException, Request
from geneweaver.aon.core.config import config
from geneweaver.aon.core.schema_version import (
    get_latest_schema_version,
    get_schema_version,
    get_schema_versions,
    set_up_sessionmanager,
    set_up_sessionmanager_by_schema,
)
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger("uvicorn.error")

DEFAULT_ALGORITHM_ID = config.DEFAULT_ALGORITHM_ID


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """Open and close the DB connection pool.

    :param app: The FastAPI application (dependency injection).
    """
    logger.info("Setting up DB connection pools.")
    schema_versions = get_schema_versions()
    app.session_managers, app.engines = set_up_sessionmanager_by_schema(schema_versions)

    if config.DEFAULT_SCHEMA is None:
        default_schema_version = get_latest_schema_version()
        default_version_id = (
            None if default_schema_version is None else default_schema_version.id
        )
        logger.info(
            f"Using latest schema version as default: {default_schema_version}."
        )
    else:
        default_version_id = next(
            (v.id for v in schema_versions if v.schema_name == config.DEFAULT_SCHEMA),
            None,
        )

    app.default_schema_version_id = default_version_id
    app.session = app.session_managers[default_version_id]

    yield

    logger.info("Closing DB connection pools.")
    for session in app.session_managers.values():
        session.close_all()
    for engine, gw_engine in app.engines.values():
        engine.dispose()
        gw_engine.dispose()


def version_id(version_id: int, request: Request) -> None:
    logger.info(f"Setting schema version to {version_id}.")
    request.state.schema_version_id = version_id


def session(request: Request) -> sessionmaker:
    """Get a session from the connection pool."""
    try:
        schema_version = request.state.schema_version_id
        try:
            session = request.app.session_managers[schema_version]()
        except KeyError:
            version = get_schema_version(schema_version)
            if version is not None and version.id not in request.app.session_managers:
                (
                    request.app.session_managers[version.id],
                    request.app.engines[version.id],
                ) = set_up_sessionmanager(version)
                session = request.app.session_managers[version.id]()
            else:
                raise HTTPException(status_code=404, detail="Schema version not found.")
    except AttributeError:
        session = request.app.session()

    yield session

    session.close()


async def paging_parameters(
    start: Annotated[Optional[int], "The item to start at (the offset)."] = None,
    limit: Annotated[int, "The number of records per page."] = 100,
) -> dict[str, Union[int, str]]:
    """Get the paging parameters.

    :param start: The item to start at (the offset).
    :param limit: The number of records per page.
    :return: The paging parameters.
    """
    return {
        "start": start,
        "limit": limit,
    }
