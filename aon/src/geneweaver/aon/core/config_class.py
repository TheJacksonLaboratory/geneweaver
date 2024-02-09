"""Config class definition."""
from typing import Any, Dict, Optional
from pydantic import BaseSettings, validator
from geneweaver.db.core.settings_class import Settings as DBSettings


class Config(BaseSettings):
    """Root Config and Settings Configuration."""
    TITLE: str = "Geneweaver Ortholog Normalizer"
    DESCRIPTION: str = "An application to aid in normalizing homology data."

    DEBUG: bool = False
    TESTING: bool = False
    LOG_LEVEL: str = "WARNING"
    API_PREFIX: str = "/aon/api"

    DB_HOST: str
    DB_USERNAME: str = ""
    DB_PASSWORD: str = ""
    DB_NAME: str
    DB_PORT: int = 5432
    DB: Optional[DBSettings] = None

    @validator("DB", pre=True)
    def assemble_aon_db_settings(
        cls, v: Optional[DBSettings], values: Dict[str, Any]  # noqa: N805
    ) -> DBSettings:
        """Build the database settings."""
        if isinstance(v, DBSettings):
            return v
        return DBSettings(
            CONNECTION_SCHEME="postgresql+psycopg",
            SERVER=values.get("DB_HOST"),
            NAME=values.get("DB_NAME"),
            USERNAME=values.get("DB_USERNAME"),
            PASSWORD=values.get("DB_PASSWORD"),
            PORT=values.get("DB_PORT"),
        )

    GW_DB_HOST: str
    GW_DB_USERNAME: str = ""
    GW_DB_PASSWORD: str = ""
    GW_DB_NAME: str
    GW_DB_PORT: int = 5432
    GW_DB: Optional[DBSettings] = None

    @validator("GW_DB", pre=True)
    def assemble_gw_db_settings(
        cls, v: Optional[DBSettings], values: Dict[str, Any]  # noqa: N805
    ) -> DBSettings:
        """Build the database settings."""
        if isinstance(v, DBSettings):
            return v
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
