"""
Application config that uses environs module to load values from .env file or environment variables
"""

import logging
from environs import Env

logger = logging.getLogger(__name__)

env = Env()
env.read_env()

class Config:
    TITLE = 'Geneweaver Ortholog Normalizer'
    VERSION = '0.0.1'
    DESCRIPTION = 'An application to aid in normalizing homology data.'

    # SECRET_KEY = env.str('SECRET_KEY')

    DEBUG = env.bool('DEBUG', default=False)
    TESTING = env.bool('TESTING', default=False)
    LOG_LEVEL = env.str("LOG_LEVEL", default="WARNING")

    # TODO - update to point to relevant databases
    DATABASE_URL_AGR = 'postgresql://user:pass@localhost:5432/agr'
    DATABASE_URL_GW = 'postgresql://user:pass@localhost:2222/geneweaver'
