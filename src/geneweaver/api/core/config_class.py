"""Namespace for the config class for the Geneweaver API."""

from geneweaver.db.core.settings_class import Settings as DBSettings
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


class GeneweaverAPIConfig(BaseSettings):
    """Config class for the Geneweaver API."""

    LOG_LEVEL: str = "INFO"

    API_PREFIX: str = "/api"

    # Browser origins allowed to call this API cross-origin. Empty by default, which
    # disables CORS entirely -- deployed environments serve the UI same-origin behind the
    # ingress and need none. Set CORS_ORIGINS for local development, e.g. the Angular dev
    # server, which serves on 4200 (`ui/project.json` serve-static, and Angular's
    # default): CORS_ORIGINS='["http://localhost:4200"]'
    # Add the port you actually used if you override it, e.g. `nx serve --port 4201`.
    CORS_ORIGINS: list[str] = []

    DB_HOST: str
    DB_USERNAME: str
    DB_PASSWORD: str
    DB_NAME: str
    DB_PORT: int = 5432
    DB: DBSettings | None = None

    @model_validator(mode="after")
    def assemble_db_settings(self) -> Self:
        """Build the database settings."""
        if not isinstance(self.DB, DBSettings):
            self.DB = DBSettings(
                SERVER=self.DB_HOST,
                NAME=self.DB_NAME,
                USERNAME=self.DB_USERNAME,
                PASSWORD=self.DB_PASSWORD,
                PORT=self.DB_PORT,
            )
        return self

    DB_POOL_MIN_SIZE: int = 4
    DB_POOL_MAX_SIZE: int = 8
    DB_POOL_MAX_LIFETIME: int = 300
    DB_POOL_MAX_IDLE: int = 60

    AUTH_DOMAIN: str = "thejacksonlaboratory.auth0.com"
    AUTH_AUDIENCE: str = "https://cube.jax.org"
    AUTH_ALGORITHMS: list[str] = ["RS256"]
    AUTH_EMAIL_CLAIM: str = "email"
    AUTH_SCOPES: dict = {
        "openid profile email": "read",
    }
    JWT_PERMISSION_PREFIX: str = "approle"
    # Used only by the Swagger docs page's "Authorize" button. Browser sign-in for `/next`
    # is AUTH_LOGIN_CLIENT_ID below.
    AUTH_CLIENT_ID: str = "aE6dpT04mGlvPeUXl4RYGSnCjvHEuawd"

    # Server-side sign-in for the `/next` UI (`controller/auth.py`), the same confidential
    # authorization-code flow legacy uses: the API holds the client secret and exchanges the
    # code, and the browser only ever holds an encrypted session cookie. Sign-in is off until
    # all four are set, so an environment without them behaves exactly as before.
    # The client is legacy's Auth0 application for the same tier (x9Ii... dev/sqa,
    # 5X9T... stage/prod), so a user signed in to either is recognised by the other.
    AUTH_LOGIN_CLIENT_ID: str | None = None
    # Secret: from a Kubernetes Secret, never a configmap, and never logged.
    AUTH_LOGIN_CLIENT_SECRET: str | None = None
    # Secret: a Fernet key (`Fernet.generate_key()`) that encrypts the session cookie.
    # Rotating it signs everyone out.
    AUTH_SESSION_KEY: str | None = None
    # The site's public origin, e.g. https://geneweaver-dev.jax.org. Builds the callback URL
    # registered with Auth0, and is the one Origin a cookie-authenticated write may come from.
    AUTH_PUBLIC_URL: str | None = None
    # Off only for local development over plain http.
    AUTH_COOKIE_SECURE: bool = True

    # AsyncTask's API root, e.g. http://asynctask-api.dev.svc.cluster.local/asynctask/api.
    # Unset by default, which keeps every tool run in-process -- so an environment only
    # sends runs to AsyncTask once its overlay sets this, and one whose AsyncTask lacks
    # the geneweaver-tools plugin is never pointed at it.
    ASYNCTASK_API_URL: str | None = None
    # How long `POST /tools/{tool}` waits for a run before answering 202 with its run id.
    ASYNCTASK_WAIT_SECONDS: float = 30.0
    ASYNCTASK_POLL_SECONDS: float = 1.0
    # Per HTTP call to AsyncTask, not per run.
    ASYNCTASK_REQUEST_TIMEOUT_SECONDS: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )
