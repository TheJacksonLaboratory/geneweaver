"""Schemas relating to species."""

import datetime
from typing import Any

from geneweaver.core.enum import GeneIdentifier
from pydantic import BaseModel, Json


class Species(BaseModel):
    """Species schema."""

    id: int
    name: str
    taxonomic_id: int
    reference_gene_identifier: GeneIdentifier | None = None


class SpeciesRow(BaseModel):
    """Species schema for database row."""

    sp_id: int
    sp_name: str
    sp_taxid: int
    sp_ref_gdb_id: int | None = None
    sp_date: datetime.date
    sp_biomart_info: str | None = None
    sp_source_data: Json[Any]
