"""User related schemas."""

import datetime

from geneweaver.core.enum import AdminLevelInt
from geneweaver.core.schema.stubgenerator import StubGenerator
from pydantic import BaseModel


class UserRequiredFields(BaseModel):
    """User schema for required fields."""

    id: int
    email: str
    prefs: str = "{}"
    is_guest: bool = False


class User(UserRequiredFields):
    """User schema."""

    first_name: str | None = None
    last_name: str | None = None
    password: str | None = None
    admin: AdminLevelInt = AdminLevelInt.NORMAL_USER
    last_seen: datetime.datetime | None = None
    create: datetime.date | None = None
    ip_address: str | None = None
    api_key: str | None = None
    sso_id: str | None = None


class UserFull(User):
    """User schema with full information."""

    groups: list[str]
    stubgenerators: list[StubGenerator]
