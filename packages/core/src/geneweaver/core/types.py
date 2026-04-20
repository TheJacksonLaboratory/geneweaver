"""A module for common complex types used by Geneweaver."""

from pathlib import Path
from typing import Union

from geneweaver.core.schema.gene import GeneValue

StringOrPath = Union[str, Path]

DictRow = dict[str, str | int]

GeneIds = list[str]

GeneIdValues = list[GeneValue]

StrainIds = list[str]
