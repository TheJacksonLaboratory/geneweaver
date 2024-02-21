"""Root database module, for uses other than the FastAPI application."""

from geneweaver.aon.core.config import config
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

BaseAGR = declarative_base()
BaseGW = declarative_base()

binds = {}
if config.DB is not None:
    agr_engine = create_engine(config.DB.URI)
    binds[BaseAGR] = agr_engine

if config.GW_DB is not None:
    gw_engine = create_engine(config.GW_DB.URI)
    binds[BaseGW] = gw_engine


SessionLocal = sessionmaker(autocommit=False, autoflush=False)
SessionLocal.configure(binds=binds)
