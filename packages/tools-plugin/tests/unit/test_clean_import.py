"""The plugin loads without the tools, the database or the scientific libraries.

AsyncTask installs this package; if loading it reached into any of these, AsyncTask would
have to install them too, which is what the plugin exists to avoid. Checked in a fresh
interpreter, because this process may already have imported them for other tests. The
publish job's clean-install smoke test checks the same from the built wheel, where they are
not installed at all.
"""

import subprocess
import sys

import pytest

#: Module prefixes the plugin must never load.
FORBIDDEN = (
    "geneweaver.tools.",
    "geneweaver.db",
    "geneweaver.core",
    "sklearn",
    "scipy",
    "numpy",
    "psycopg",
    "pydantic",
)


@pytest.mark.parametrize(
    "module",
    [
        "geneweaver.tools_plugin",
        "geneweaver.tools_plugin.contract",
        "geneweaver.tools_plugin.payload",
        "geneweaver.tools_plugin.workflows",
    ],
)
def test_loading_the_plugin_loads_nothing_it_should_not(module: str) -> None:
    """Import one plugin module, then list anything forbidden that came with it."""
    probe = (
        "import importlib, sys\n"
        f"importlib.import_module({module!r})\n"
        f"forbidden = {FORBIDDEN!r}\n"
        "loaded = sorted(name for name in sys.modules\n"
        "                if name.startswith(forbidden) or name == 'geneweaver.tools')\n"
        "print(','.join(loaded))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "", f"{module} loaded {result.stdout.strip()}"
