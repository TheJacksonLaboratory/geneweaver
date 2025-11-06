import os
import binascii
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


## Global config object, sholudn't be accessed directly but using the helper
## functions found below.
CONFIG = None


class ApplicationConfig(BaseModel):

    host: str = "127.0.0.1"
    results: str = "/var/geneweaver/results"
    secret: str = binascii.hexlify(os.urandom(32)).decode()
    help_url: str = "http://geneweaver.org/help"
    smtp: str = "smtp.jax.org"
    admin_email: str = "noreply@geneweaver.org"


class Celery(BaseModel):
    # Broker configuration
    transport: str = "redis"
    host: str = "localhost"
    port: int = 6379
    user: str = ""
    password: str = ""
    db: int = 0
    url: Optional[str] = Field(None, validate_default=True)

    # Backend configuration
    backend: Optional[str] = Field(None, validate_default=True)
    result_backend_transport: str = "redis"
    result_backend_host: Optional[str] = None
    result_backend_port: Optional[int] = None
    result_backend_user: Optional[str] = None
    result_backend_password: Optional[str] = None
    result_backend_db: Optional[int] = None

    @model_validator(mode='after')
    def url_validator(self):
        # Construct broker URL if not explicitly provided
        if self.url is None:
            if self.password:
                credentials = f"{self.user}:{self.password}@"
            elif self.user:
                credentials = f"{self.user}@"
            else:
                credentials = ""
            db = f"/{self.db}" if self.db else ""
            self.url = f"{self.transport}://{credentials}{self.host}:{self.port}{db}"

        # Construct backend URL if not explicitly provided
        if self.backend is None:
            # Use backend-specific values, fall back to broker values if not set
            backend_host = self.result_backend_host if self.result_backend_host is not None else self.host
            backend_port = self.result_backend_port if self.result_backend_port is not None else self.port
            backend_user = self.result_backend_user if self.result_backend_user is not None else self.user
            backend_password = self.result_backend_password if self.result_backend_password is not None else self.password
            backend_db = self.result_backend_db if self.result_backend_db is not None else self.db

            if backend_password:
                backend_credentials = f"{backend_user}:{backend_password}@"
            elif backend_user:
                backend_credentials = f"{backend_user}@"
            else:
                backend_credentials = ""
            backend_db_str = f"/{backend_db}" if backend_db else ""
            self.backend = f"{self.result_backend_transport}://{backend_credentials}{backend_host}:{backend_port}{backend_db_str}"

        return self

class DB(BaseModel):

    host: str = Field("127.0.0.1")
    database: str = Field("geneweaver", validation_alias="name")
    user: str = Field("postgres", validation_alias="username")
    password: str = Field("postgres")
    port: int = Field(5432)


class Sphinx(BaseModel):

    host: str = "127.0.0.1"
    port: int = 9312


class LandingPage(BaseModel):

    apikey_geneweaver: str = "apikey"
    agr_url: str = "https://www.alliancegenome.org/api/"
    api_key_disgenet: str = "apikey"
    api_host_disgenet: str = "https://www.disgenet.org/api"


class Auth(BaseModel):
    client_id: str = Field("x9IiBRyt8lS3lsqrz2H6aO1leRBbxyb7", validation_alias="clientid")
    client_secret: str = Field("", validation_alias="clientsecret")
    domain: str = "thejacksonlaboratory.auth0.com"
    auth_endpoint: str = Field("authorize", validation_alias="authendpoint")
    token_endpoint: str = Field("oauth/token", validation_alias="tokenendpoint")
    userinfo_endpoint: str = Field("oauth/userinfo", validation_alias="userinfoendpoint")
    jwks_endpoint: str = Field(".well-known/jwks.json", validation_alias="jwksendpoint")
    audience: str = "https://cube.jax.org"


class GeneweaverLegacyConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_nested_delimiter='_',
        env_file='.env',
        env_file_encoding='utf-8'
    )

    application: ApplicationConfig = ApplicationConfig()
    celery: Celery = Celery()
    db: DB = DB()
    sphinx: Sphinx = Sphinx()
    landing_page: LandingPage = LandingPage()
    auth: Auth = Auth()

    def get(self, section, option):
        return getattr(
            getattr(self, section),
            option
        )

    def set(self, section, option, value):
        setattr(
            getattr(self, section),
            option,
            value
        )

    def getint(self, section, option):
        return int(self.get(section, option))

    def items(self, section):
        return getattr(self, section).dict().items()

    def keys(self, section):
        return getattr(self, section).dict().keys()

    def values(self, section):
        return getattr(self, section).dict().values()


def get(section, option) -> Any:
    """
    Returns the value of a section, key pair from the global config object.

    :returns some config value
    """

    return CONFIG.get(section, option)


def getInt(section, option) -> int:
    """
    Returns the value of a section, key pair from the global config object as
    an int.

    :returns int: some config value
    """

    return CONFIG.getint(section, option)


## This config module should be included prior to any others since other parts
## of the app may need to access its variables. The config will attempt to load
## and parse everything as soon as it's imported.
if not CONFIG:
    CONFIG = GeneweaverLegacyConfig()
