"""Schemas for API Responses."""

from pydantic import AnyUrl, BaseModel


class PagingLinks(BaseModel):
    """Schema for holding paging links."""

    first: AnyUrl | None = None
    previous: AnyUrl | None = None
    next: AnyUrl | None = None
    last: AnyUrl | None = None


class Paging(BaseModel):
    """Schema for paging information."""

    page: int | None = None
    items: int | None = None
    total_pages: int | None = None
    total_items: int | None = None
    links: PagingLinks | None = None


class CollectionResponse(BaseModel):
    """Schema for API responses with collections."""

    data: list
    paging: Paging | None = None
