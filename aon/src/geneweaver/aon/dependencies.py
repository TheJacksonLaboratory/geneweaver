"""Dependency injection for the AON FastAPI application."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from geneweaver.aon.core.config import config
from geneweaver.aon.core.database import BaseAGR, BaseGW
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """Open and close the DB connection pool.

    :param app: The FastAPI application (dependency injection).
    """
    logger.info("Setting up DB connection pool.")
    app.aon_engine = create_engine(config.DB.URI)
    app.gw_engine = create_engine(config.GW_DB.URI)

    app.session = sessionmaker(autocommit=False, autoflush=False)
    app.session.configure(binds={BaseAGR: app.aon_engine, BaseGW: app.gw_engine})

    yield

    logger.info("Closing DB connection pool.")

    app.session.close_all()
    app.aon_engine.dispose()
    app.gw_engine.dispose()


def session(request: Request) -> sessionmaker:
    """Get a session from the connection pool."""
    return request.app.session()


from typing import Annotated, Optional, Union


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
