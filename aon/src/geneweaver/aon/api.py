"""The root of the GeneWeaver AON API."""

from fastapi import APIRouter, Depends, FastAPI
from geneweaver.aon import __version__
from geneweaver.aon import dependencies as deps
from geneweaver.aon.controller import (
    algorithms,
    genes,
    homologs,
    orthologs,
    species,
    versions,
)
from geneweaver.aon.core.config import config

app = FastAPI(
    title="GeneWeaver AON API",
    version=__version__,
    docs_url=f"{config.API_PREFIX}/docs",
    redoc_url=f"{config.API_PREFIX}/redoc",
    openapi_url=f"{config.API_PREFIX}/openapi.json",
    lifespan=deps.lifespan,
    prefix=config.API_PREFIX,
)

app.include_router(versions.router, prefix=config.API_PREFIX, tags=["versions"])

api_router = APIRouter()

api_router.include_router(algorithms.router, tags=["algorithms"])
api_router.include_router(species.router, tags=["species"])
api_router.include_router(genes.router, tags=["genes"])
api_router.include_router(orthologs.router, tags=["orthologs"])
api_router.include_router(homologs.router, tags=["homologs"])

versioned_api_router = APIRouter(tags=["versioned"])
versioned_api_router.include_router(
    api_router, prefix="/{version_id}", dependencies=[Depends(deps.version_id)]
)

app.include_router(api_router, prefix=config.API_PREFIX)
app.include_router(versioned_api_router, prefix=config.API_PREFIX)
