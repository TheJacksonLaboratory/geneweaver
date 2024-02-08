from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from geneweaver.aon.core.config import config

agr_engine = create_engine(config.DB.URI)
gw_engine = create_engine(config.GW_DB.URI)

BaseAGR = declarative_base()
BaseGW = declarative_base()

SessionLocal = sessionmaker(autocommit=False, autoflush=False)
SessionLocal.configure(binds={BaseAGR: agr_engine, BaseGW: gw_engine})
