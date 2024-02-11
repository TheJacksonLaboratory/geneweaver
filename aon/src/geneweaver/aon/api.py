""""""

from fastapi import APIRouter, FastAPI
from geneweaver.aon import __version__
from geneweaver.aon import dependencies as deps
from geneweaver.aon.core.config import config
from geneweaver.aon.controller import algorithms, species, genes, orthologs, homologs

app = FastAPI(
    title="GeneWeaver AON API",
    version=__version__,
    docs_url=f"{config.API_PREFIX}/docs",
    redoc_url=f"{config.API_PREFIX}/redoc",
    openapi_url=f"{config.API_PREFIX}/openapi.json",
    lifespan=deps.lifespan,
)

api_router = APIRouter()

api_router.include_router(algorithms.router)

app.include_router(api_router, prefix=config.API_PREFIX)
app.include_router(species.router, prefix=config.API_PREFIX)
app.include_router(genes.router, prefix=config.API_PREFIX)
app.include_router(orthologs.router, prefix=config.API_PREFIX)
app.include_router(homologs.router, prefix=config.API_PREFIX)
