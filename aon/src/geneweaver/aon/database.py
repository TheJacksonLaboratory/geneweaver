from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from geneweaver.aon.config import Config

agr_engine = create_engine(Config.DATABASE_URL_AGR)
gw_engine = create_engine(Config.DATABASE_URL_GW)

BaseAGR = declarative_base()
BaseGW = declarative_base()

SessionLocal = sessionmaker(autocommit=False, autoflush=False)
SessionLocal.configure(binds={BaseAGR: agr_engine, BaseGW: gw_engine})

