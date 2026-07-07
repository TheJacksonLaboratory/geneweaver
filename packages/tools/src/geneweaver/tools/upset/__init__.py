"""UpSet tool (gene-set intersection sizes per combination)."""

from .schema import UpSetInput, UpSetIntersection, UpSetOutput
from .tool import UpSet, intersection_sizes

__all__ = [
    "UpSet",
    "UpSetInput",
    "UpSetIntersection",
    "UpSetOutput",
    "intersection_sizes",
]
