"""`geneweaver` must stay a PEP 420 namespace package.

Five first-party distributions install into `geneweaver/`: the root `geneweaver-api`,
plus `geneweaver-core`, `geneweaver-db`, `geneweaver-client` and `geneweaver-tools`
from `packages/`. They can only coexist because `geneweaver` is a namespace package
rather than a regular one.

Adding an `__init__.py` to any single distribution's `src/geneweaver/` turns that
portion into a regular package and shadows the rest: the offending distribution keeps
importing fine, while the other four silently stop resolving. The symptom then appears
far from its cause -- usually as an `ImportError` in an unrelated package's tests -- so
it is worth asserting directly.

This replaces the equivalent check that used to come from the archived
`geneweaver-testing` package. Paths are derived from this file rather than from
pytest's `rootdir`, because CI runs the root suite from the repository root and each
package suite from inside that package's own directory, which moves `rootdir`.
"""

import importlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Every distribution source root that contributes a portion to the namespace. Globbed
#: rather than hard-coded so a newly added package is covered without editing this file.
NAMESPACE_SOURCE_ROOTS = [
    REPO_ROOT / "src",
    *sorted((REPO_ROOT / "packages").glob("*/src")),
]

#: The subpackage each distribution provides under the `geneweaver` namespace.
FIRST_PARTY_SUBPACKAGES = ["api", "core", "db", "client", "tools"]


def _relative(path: Path) -> str:
    """Render a path relative to the repository root, for readable test ids."""
    return str(path.relative_to(REPO_ROOT))


def test_namespace_source_roots_are_found() -> None:
    """Guard the discovery itself, so the checks below cannot vacuously pass."""
    assert len(NAMESPACE_SOURCE_ROOTS) >= len(FIRST_PARTY_SUBPACKAGES), (
        f"Expected at least {len(FIRST_PARTY_SUBPACKAGES)} distribution source roots, "
        f"found {[_relative(p) for p in NAMESPACE_SOURCE_ROOTS]}"
    )


@pytest.mark.parametrize("source_root", NAMESPACE_SOURCE_ROOTS, ids=_relative)
def test_geneweaver_portion_is_not_a_regular_package(source_root: Path) -> None:
    """No distribution may add an `__init__.py` to the shared namespace directory."""
    init_file = source_root / "geneweaver" / "__init__.py"
    assert not init_file.exists(), (
        f"{_relative(init_file)} must not exist. It would make this distribution's "
        "`geneweaver` portion a regular package and shadow every other distribution "
        "sharing the namespace, breaking their imports."
    )


def test_geneweaver_is_a_namespace_package() -> None:
    """The imported `geneweaver` package has no `__file__`, as namespace packages do."""
    import geneweaver

    assert getattr(geneweaver, "__file__", None) is None, (
        "`geneweaver` resolved to a regular package "
        f"({geneweaver.__file__}). Only one distribution's portion is now importable; "
        "check for a stray `src/geneweaver/__init__.py`."
    )


@pytest.mark.parametrize("subpackage", FIRST_PARTY_SUBPACKAGES)
def test_first_party_subpackage_is_importable(subpackage: str) -> None:
    """Each distribution resolves through the shared namespace."""
    module = importlib.import_module(f"geneweaver.{subpackage}")
    assert module is not None
