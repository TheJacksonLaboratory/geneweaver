"""The root API definition for the GeneWeaver API.

This file defines the root API for the GeneWeaver API. It is responsible for
defining the FastAPI application and including all other API routers.
"""

from fastapi import APIRouter, FastAPI, Security
from fastapi.middleware.cors import CORSMiddleware

from geneweaver.api import __version__
from geneweaver.api import dependencies as deps
from geneweaver.api.controller import (
    genes,
    genesets,
    monitors,
    publications,
    search,
    species,
    tools,
)
from geneweaver.api.core.config import settings

app = FastAPI(
    title="GeneWeaver API",
    version=__version__,
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    swagger_ui_oauth2_redirect_url=f"{settings.API_PREFIX}/docs/oauth2-redirect",
    swagger_ui_init_oauth={
        "clientId": settings.AUTH_CLIENT_ID,
        "scopes": list(settings.AUTH_SCOPES.keys()),
    },
    lifespan=deps.lifespan,
)

# Cross-origin access for the `/next` UI when it is served from somewhere other than this
# API's origin -- in practice the Angular dev server. Driven by CORS_ORIGINS and empty by
# default, so deployed environments (same-origin behind the ingress) add no middleware at
# all and no origin list is baked into the image.
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

api_router = APIRouter(
    dependencies=[
        Security(deps.auth.implicit_scheme),
    ],
)
api_router.include_router(genesets.router)
api_router.include_router(genes.router)
api_router.include_router(publications.router)
api_router.include_router(species.router)
api_router.include_router(search.router)
api_router.include_router(monitors.router)
api_router.include_router(tools.router)

app.include_router(api_router, prefix=settings.API_PREFIX)
