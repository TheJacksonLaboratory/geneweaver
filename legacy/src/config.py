import os
import binascii
from typing import Any

from pydantic import BaseModel, Field
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

    url: str = "amqp://geneweaver:geneweaver@localhost:5672/geneweaver"
    backend: str = "amqp"


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
    client_id: str = Field("wMjx3nGV24qneBjXqz52IhEpq6AU7reo", validation_alias="clientid")
    client_secret: str = Field("", validation_alias="clientsecret")
    domain: str = "geneweaver.auth0.com"
    auth_endpoint: str = Field("authorize", validation_alias="authendpoint")
    token_endpoint: str = Field("oauth/token", validation_alias="tokenendpoint")
    userinfo_endpoint: str = Field("oauth/userinfo", validation_alias="userinfoendpoint")
    jwks_endpoint: str = Field(".well-known/jwks.json", validation_alias="jwksendpoint")


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
