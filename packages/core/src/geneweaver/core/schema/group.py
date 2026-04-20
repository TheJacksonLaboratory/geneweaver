"""Group schemas."""

import datetime

from geneweaver.core.schema.stubgenerator import StubGenerator
from pydantic import BaseModel


class Group(BaseModel):
    """Group schema."""

    id: int
    name: str
    private: bool
    created: datetime.date
    stubgenerators: list[StubGenerator]


class UserAdminGroup(BaseModel):
    """User admin group schema."""

    name: str
    public: bool
    created: datetime.date
