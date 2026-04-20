"""Models for API requests."""

from collections.abc import Iterable
from enum import Enum
from typing import Generic, TypeVar

from geneweaver.core.enum import GeneIdentifier, Species
from geneweaver.core.schema.gene import Gene as GeneSchema
from geneweaver.core.schema.geneset import GeneValue as GeneValueSchema
from geneweaver.core.schema.species import Species as SpeciesSchema
from pydantic import AnyUrl, BaseModel

T = TypeVar("T")


class PagingLinks(BaseModel):
    """Schema for holding paging links."""

    first: AnyUrl | None = None
    previous: AnyUrl | None = None
    next_page: AnyUrl | None = None
    last_page: AnyUrl | None = None


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


class GeneIdMappingResp(BaseModel):
    """Model for gene id mapping response."""

    gene_ids_map: list[dict]


class GeneIdHomologReq(BaseModel):
    """Model for homolog gene id mapping request."""

    source_ids: Iterable[str]
    target_gene_id_type: GeneIdentifier
    source_gene_id_type: GeneIdentifier | None = None
    target_species: Species | None = None
    source_species: Species | None = None


class GeneIdMappingReq(BaseModel):
    """Model for gene id mapping request."""

    source_ids: list[str]
    target_gene_id_type: GeneIdentifier
    species: Species


class GeneIdMappingAonReq(BaseModel):
    """Model for AON gene id mapping request."""

    source_ids: list[str]
    species: Species


class GeneReturn(CollectionResponse):
    """Model for gene endpoint return."""

    data: list[GeneSchema]


class SpeciesReturn(CollectionResponse):
    """Model for Species endpoint return."""

    data: list[SpeciesSchema]


class GeneValueReturn(BaseModel):
    """Model for geneset values endpoint return."""

    data: list[GeneValueSchema]


class NewPubmedRecord(BaseModel):
    """Model returned for adding new pubmed info into DB."""

    pub_id: int
    pubmed_id: int


class GsPubSearchType(str, Enum):
    """Enum model for genesets and publication search types."""

    GENESETS = "genesets"
    PUBLICATIONS = "publications"


class SearchResponse(CollectionResponse, Generic[T]):
    """Model for search response endpoint."""

    data: list[T]

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the search response model.

        First argument is assigned to `data`.
        """
        if args:
            kwargs["data"] = args[0]
        super().__init__(**kwargs)


class CombinedSearchResponse(BaseModel, Generic[T]):
    """Model for combined search response endpoint."""

    object: dict[str, list[T]]

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the combined search response model.

        First argument is assigned to `object`.
        """
        if args:
            kwargs["object"] = args[0]
        super().__init__(**kwargs)
