"""Stub generator schemas."""

from pydantic import BaseModel


class StubGenerator(BaseModel):
    """Stub generator schema."""

    id: int
    name: str
    querystring: str
    last_update: str
