"""GeneWeaver Client configuration module."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


class Settings(BaseSettings):
    """Settings class for GeneWeaver Client."""

    AUTH_DOMAIN: str = "thejacksonlaboratory.auth0.com"
    AUTH_CLIENT_ID: str = "f8QZPcIrPIG6DIeWR2Rr3C8X5bzx8zBz"
    AUTH_ALGORITHMS: list[str] = ["RS256"]
    AUTH_SCOPES: list[str] = ["openid", "profile", "email", "offline_access"]
    AUTH_AUDIENCE: str = "https://cube.jax.org"

    API_HOST: str = "https://geneweaver.jax.org"
    API_PATH: str = "/api"
    AON_API_PATH: str = "/aon/api"

    API_URL: str | None = None
    AON_API_URL: str | None = None

    GEDB: str | None = None

    API_KEY: str | None = None

    @model_validator(mode="after")
    def assemble_api_urls(self) -> Self:
        """Build the API URLs."""
        if not self.API_URL:
            self.API_URL = self.API_HOST + self.API_PATH
        if not self.AON_API_URL:
            self.AON_API_URL = self.API_HOST + self.AON_API_PATH
        if not self.GEDB:
            self.GEDB = self.API_HOST + "/gedb"
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )
