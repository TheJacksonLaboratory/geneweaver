"""Config class definition."""

import logging
from typing import Any, Dict, Optional

from geneweaver.db.core.settings_class import Settings as DBSettings
from pydantic import BaseSettings, validator

logger = logging.getLogger("uvicorn.error")


class Config(BaseSettings):
    """Root Config and Settings Configuration."""

    TITLE: str = "Geneweaver Ortholog Normalizer"
    DESCRIPTION: str = "An application to aid in normalizing homology data."

    DEBUG: bool = False
    TESTING: bool = False
    LOG_LEVEL: str = "WARNING"
    API_PREFIX: str = "/aon/api"
    DEFAULT_SCHEMA: Optional[str] = None
    DEFAULT_ALGORITHM_ID: Optional[int] = 2
    TEMPORAL_NAMESPACE: str = "agr-load-data"
    TEMPORAL_TASK_QUEUE: str = "geneweaver-aon-tasks"
    TEMPORAL_URI: str = "localhost:7233"

    DB_HOST: Optional[str] = None
    DB_USERNAME: str = ""
    DB_PASSWORD: str = ""
    DB_NAME: Optional[str] = None
    DB_PORT: int = 5432
    DB: Optional[DBSettings] = None

    @validator("DB", pre=True)
    def assemble_aon_db_settings(
        cls, v: Optional[DBSettings], values: Dict[str, Any]  # noqa: N805
    ) -> Optional[DBSettings]:
        """Build the database settings."""
        if isinstance(v, DBSettings):
            return v
        elif values.get("DB_HOST") is None or values.get("DB_NAME") is None:
            logger.warning(
                "DB_HOST and DB_NAME are not set. "
                "These config values are required for database interaction!"
            )
            return None

        return DBSettings(
            CONNECTION_SCHEME="postgresql+psycopg",
            SERVER=values.get("DB_HOST"),
            NAME=values.get("DB_NAME"),
            USERNAME=values.get("DB_USERNAME"),
            PASSWORD=values.get("DB_PASSWORD"),
            PORT=values.get("DB_PORT"),
        )

    GW_DB_HOST: Optional[str] = None
    GW_DB_USERNAME: str = ""
    GW_DB_PASSWORD: str = ""
    GW_DB_NAME: Optional[str] = None
    GW_DB_PORT: int = 5432
    GW_DB: Optional[DBSettings] = None

    @validator("GW_DB", pre=True)
    def assemble_gw_db_settings(
        cls, v: Optional[DBSettings], values: Dict[str, Any]  # noqa: N805
    ) -> Optional[DBSettings]:
        """Build the database settings."""
        if isinstance(v, DBSettings):
            return v
        elif values.get("GW_DB_HOST") is None or values.get("GW_DB_NAME") is None:
            logger.warning(
                "GW_DB_HOST and GW_DB_NAME are not set. "
                "These config values are required for Geneweaver database interaction!"
            )
            return None

        return DBSettings(
            CONNECTION_SCHEME="postgresql+psycopg",
            SERVER=values.get("GW_DB_HOST"),
            NAME=values.get("GW_DB_NAME"),
            USERNAME=values.get("GW_DB_USERNAME"),
            PASSWORD=values.get("GW_DB_PASSWORD"),
            PORT=values.get("GW_DB_PORT"),
        )

    class Config:
        """Configuration for the BaseSettings class."""

        env_file = ".env"
        case_sensitive = True
