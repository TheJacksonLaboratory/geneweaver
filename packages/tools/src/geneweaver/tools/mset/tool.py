"""MSET tool, reimplemented on the AbstractTool framework.

Ported from the legacy Celery worker ``legacy/tools-worker/tools/MSET.py``, which shells out
to the ``TOOLBOX/CS_Mset/MSETcpp`` binary.

Binary-wrapper pattern (same as DBSCAN): the pure parts -- the gene-list intersection and
parsing the binary's TSV outputs -- are standalone functions; the binary invocation goes
through an injectable ``runner`` (write temp gene-list files, run MSETcpp, read
``mset_output.tsv`` / ``mset_hist.tsv``), so the tool is unit-testable without the binary.

Bug fix vs legacy: the legacy used ``group_1_background`` for *both* lists (copy-paste bug);
here ``group_2_genes`` correctly uses ``group_2_background``.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Callable

from geneweaver.tools.framework.abstract import AbstractTool

from .schema import MSETInput, MSETOutput

# A runner takes (g1, g2, bg1_name, bg2_name, n_samples, over) and returns the raw text of
# the binary's two output files: (mset_output.tsv, mset_hist.tsv).
MSETRunner = Callable[[list[str], list[str], str, str, int, bool], tuple[str, str]]

BINARY_ENV_VAR = "GENEWEAVER_MSET_BINARY"
BACKGROUND_ENV_VAR = "GENEWEAVER_MSET_BACKGROUND_DIR"


def intersect_genes(group_1: list[str], group_2: list[str]) -> list[str]:
    """Genes present in both lists, in the order they appear in group 1 (deduplicated)."""
    in_group_2 = {str(g) for g in group_2}
    seen: set[str] = set()
    out: list[str] = []
    for gene in group_1:
        g = str(gene)
        if g in in_group_2 and g not in seen:
            seen.add(g)
            out.append(g)
    return out


def parse_tsv_dict(text: str) -> dict[str, str]:
    """Parse the binary's tab-separated key/value output into a dict."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        result[parts[0]] = parts[1].strip() if len(parts) > 1 else ""
    return result


def _subprocess_runner(binary_path: str, background_dir: str) -> MSETRunner:
    """Default runner: write gene lists to temp files, run MSETcpp, read its TSV outputs."""

    def run(
        g1: list[str], g2: list[str], bg1: str, bg2: str, n_samples: int, over: bool
    ) -> tuple[str, str]:
        workdir = tempfile.mkdtemp(prefix="mset_")
        f1 = os.path.join(workdir, "group_1.txt")
        f2 = os.path.join(workdir, "group_2.txt")
        for path, genes in ((f1, g1), (f2, g2)):
            with open(path, "w") as handle:
                handle.write("\n".join(str(gene) for gene in genes) + "\n")
        cmd = [
            binary_path,
            str(n_samples),
            f1,
            os.path.join(background_dir, bg1),
            f2,
            os.path.join(background_dir, bg2),
            "-O" if over else "-U",
        ]
        result = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"MSET binary failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        with open(os.path.join(workdir, "mset_output.tsv")) as handle:
            data = handle.read()
        with open(os.path.join(workdir, "mset_hist.tsv")) as handle:
            hist = handle.read()
        return data, hist

    return run


class MSET(AbstractTool):
    """Modular Single-set Enrichment Test between two gene lists (wraps the MSET binary)."""

    def __init__(
        self,
        binary_path: str | None = None,
        background_dir: str | None = None,
        runner: MSETRunner | None = None,
    ) -> None:
        """Configure how the MSET binary is located/invoked (or inject a runner for tests)."""
        self._binary_path = binary_path or os.environ.get(BINARY_ENV_VAR)
        self._background_dir = background_dir or os.environ.get(BACKGROUND_ENV_VAR, "")
        self._runner = runner

    @property
    def tool_input(self) -> type[MSETInput]:
        """Input schema for the tool."""
        return MSETInput

    @property
    def tool_output(self) -> type[MSETOutput]:
        """Output schema for the tool."""
        return MSETOutput

    def _run_binary(self, tool_input: MSETInput) -> tuple[str, str]:
        runner = self._runner
        if runner is None:
            if not self._binary_path:
                raise RuntimeError(
                    f"MSET binary not configured: set {BINARY_ENV_VAR} (and "
                    f"{BACKGROUND_ENV_VAR}), or pass binary_path/runner."
                )
            runner = _subprocess_runner(self._binary_path, self._background_dir)
        return runner(
            tool_input.group_1_genes,
            tool_input.group_2_genes,
            tool_input.group_1_background,
            tool_input.group_2_background,
            tool_input.number_of_samples,
            tool_input.over_representation,
        )

    def run(self, tool_input: MSETInput) -> MSETOutput:
        """Run MSET over the two gene lists and parse the binary's outputs."""
        data_text, hist_text = self._run_binary(tool_input)
        return MSETOutput(
            intersect_genes=intersect_genes(tool_input.group_1_genes, tool_input.group_2_genes),
            mset_data=parse_tsv_dict(data_text),
            mset_hist=parse_tsv_dict(hist_text),
        )
