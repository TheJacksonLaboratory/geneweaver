"""Models needed to work with the legacy API."""

from geneweaver.core.enum import GenesetAccess, ScoreType
from pydantic import BaseModel, ConfigDict, HttpUrl


class AddGenesetByUserPublication(BaseModel):
    """Publication schema for adding genesets by user."""

    pub_abstract: str | None = None
    pub_authors: str | None = None
    pub_journal: str | None = None
    pub_pages: str | None = None
    pub_pubmed: str | None = None
    pub_title: str | None = None
    pub_volume: str | None = None
    pub_year: str | None = None


class AddGenesetByUserBase(BaseModel):
    """Base schema for adding genesets by user."""

    gene_identifier: str
    gs_abbreviation: str
    gs_description: str
    gs_name: str
    gs_threshold_type: ScoreType
    permissions: GenesetAccess
    publication: AddGenesetByUserPublication | None = None
    select_groups: list[str]
    sp_id: str
    model_config = ConfigDict(use_enum_values=True)


class AddGenesetByUser(AddGenesetByUserBase):
    """Schema for adding genesets by user."""

    file_text: str


class AddGenesetByUserFile(AddGenesetByUserBase):
    """Schema for adding genesets by user from file."""

    file_url: HttpUrl
