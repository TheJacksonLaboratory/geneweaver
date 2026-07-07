"""DBSCAN tool: cluster genes by gene-set co-membership.

The default ``DBSCAN`` is the **in-process** scipy+sklearn implementation (requires the
``sklearn`` extra) — validated identical to the legacy C++ binary and far faster
(see ``docs/tools/TOOLS_BENCHMARKS.md`` §1). The compiled-binary wrapper is available as
``BinaryDBSCAN`` and needs no extra dependencies.

``DBSCAN`` (and its back-compat alias ``SklearnDBSCAN``) are imported lazily so that
``BinaryDBSCAN`` and the pure encode/decode helpers stay importable without scipy/sklearn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .schema import DBSCANInput, DBSCANOutput
from .tool import BinaryDBSCAN, decode_clusters, encode_bipartite

if TYPE_CHECKING:  # for type checkers / IDEs, without importing scipy at runtime
    from .sklearn_tool import DBSCAN, SklearnDBSCAN

__all__ = [
    "DBSCAN",
    "BinaryDBSCAN",
    "DBSCANInput",
    "DBSCANOutput",
    "SklearnDBSCAN",
    "decode_clusters",
    "encode_bipartite",
]


def __getattr__(name: str):  # PEP 562: lazy-load the scipy/sklearn default on first access.
    """Resolve ``DBSCAN``/``SklearnDBSCAN`` lazily (they require the ``sklearn`` extra)."""
    if name in ("DBSCAN", "SklearnDBSCAN"):
        from .sklearn_tool import DBSCAN

        return DBSCAN
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
