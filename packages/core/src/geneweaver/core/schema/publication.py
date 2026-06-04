"""Publication schemas."""

from pydantic import BaseModel


class PublicationInfo(BaseModel):
    """Publication upload schema (no ID)."""

    pubmed_id: int
    authors: str
    title: str
    abstract: str = ""
    journal: str | None = None
    volume: str | None = None
    pages: str | None = None
    month: str | None = None
    year: int | str | None = None


class Publication(PublicationInfo):
    """Publication schema (with ID)."""

    id: int
