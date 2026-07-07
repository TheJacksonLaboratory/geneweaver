"""HyperGeometric tool (Fisher's exact test over gene-set pairs)."""

from .schema import (
    ContingencyCounts,
    HyperGeometricInput,
    HyperGeometricOutput,
    HyperGeometricResult,
)
from .tool import HyperGeometric, fisher_exact_2x2

__all__ = [
    "ContingencyCounts",
    "HyperGeometric",
    "HyperGeometricInput",
    "HyperGeometricOutput",
    "HyperGeometricResult",
    "fisher_exact_2x2",
]
