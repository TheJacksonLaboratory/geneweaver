"""Authentication Related Schemas."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AppRoles(str, Enum):
    """Roles that a user can have in the GeneWeaver application."""

    user = "user"
    curator = "curator"
    admin = "admin"


class User(BaseModel):
    """User model."""

    email: str | None = None
    name: str | None = None
    sso_id: str = Field(None, alias="sub")
    id: int = Field(None, alias="gw_id")
    role: AppRoles | None = AppRoles.user


class UserInternal(User):
    """Internal User model."""

    auth_header: dict = {}
    token: str
    permissions: list[str] | None = None

    model_config = ConfigDict(populate_by_name=True)
