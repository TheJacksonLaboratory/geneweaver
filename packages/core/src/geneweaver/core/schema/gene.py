"""Gene schema."""

import datetime
from typing import Any

from geneweaver.core.enum import GeneIdentifier, Species
from pydantic import BaseModel, ConfigDict


class Gene(BaseModel):
    """Gene schema."""

    id: int
    reference_id: str
    gene_database: GeneIdentifier
    species: Species
    preferred: bool
    date: datetime.date


class GeneRow(BaseModel):
    """Gene schema for database row."""

    ode_gene_id: int
    ode_ref_id: str
    gdb_id: int
    sp_id: int
    ode_pref: bool
    ode_date: str | None = None
    old_ode_gene_ids: list[int] | None = None


class GeneValue(BaseModel):
    """A gene value."""

    symbol: str
    value: float
    model_config = ConfigDict(frozen=True)

    def __str__(self: "GeneValue") -> str:
        """Return the gene symbol."""
        return f"{self.symbol}\t{self.value}"

    def __hash__(self: "GeneValue") -> int:
        """Hash the gene symbol (without value)."""
        # TODO note about hashing collisions
        return hash(self.symbol)

    def __eq__(self: "GeneValue", other: Any) -> bool:
        """Compare the gene symbol (without value)."""
        if isinstance(other, GeneValue):
            return self.symbol == other.symbol
        return False


class GeneDatabase(BaseModel):
    """Gene database schema."""

    name: str
    shortname: str
    species: str
    data: datetime.datetime
    precision: int


class GeneDatabaseRow(BaseModel):
    """Gene database schema for database row."""

    gdb_id: int
    gdb_name: str
    sp_id: int
    gdb_shortname: str
    gdb_date: str
    gdb_precision: int
    gdb_linkout_url: str | None = None
