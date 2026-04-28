"""A module for common complex types used by Geneweaver."""

from pathlib import Path

from geneweaver.core.schema.gene import GeneValue

StringOrPath = str | Path

DictRow = dict[str, str | int]

GeneIds = list[str]

GeneIdValues = list[GeneValue]

StrainIds = list[str]
