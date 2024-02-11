"""Dependency injection for the AON FastAPI application."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base

from geneweaver.aon.core.config import config
from geneweaver.aon.core.database import BaseAGR, BaseGW

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
