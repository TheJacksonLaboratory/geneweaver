"""MSET tool, reimplemented on the AbstractTool framework.

Ported from the legacy Celery worker ``legacy/tools-worker/tools/MSET.py``, which shells out
to the ``TOOLBOX/CS_Mset/MSETcpp`` binary.

Binary-wrapper pattern (same as DBSCAN): the pure parts -- the gene-list intersection, the
background subset check and parsing the binary's TSV outputs -- are standalone functions; the
binary invocation goes through an injectable ``runner`` (write temp files, run MSETcpp, read
``mset_output.tsv`` / ``mset_hist.tsv``), so the tool is unit-testable without the binary.

Two fixes vs legacy:

* the legacy used ``group_1_background`` for *both* lists (copy-paste bug); here ``group_2_genes``
  correctly uses ``group_2_background``;
* the backgrounds arrive as **resolved gene universes** rather than names of precomputed
  ``*BG.txt`` files. MSETcpp still needs them on disk, so the runner materialises them as temp
  files -- but nothing is read from a background directory and no such files ship in any image.
  See ``schema.MSETInput`` and G3-784 for why the static files were wrong on two counts.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable

from geneweaver.tools.framework.abstract import AbstractTool

from .schema import MSETInput, MSETOutput

# A runner takes (g1, g2, bg1, bg2, n_samples, over) -- all four gene collections as lists --
# and returns the raw text of the binary's two output files: (mset_output.tsv, mset_hist.tsv).
MSETRunner = Callable[[list[str], list[str], list[str], list[str], int, bool], tuple[str, str]]

BINARY_ENV_VAR = "GENEWEAVER_MSET_BINARY"

#: How many offending genes to name in the subset-check error before truncating.
_MAX_REPORTED_GENES = 10


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


def genes_outside_background(genes: list[str], background: list[str]) -> list[str]:
    """Genes absent from the background universe, deduplicated, in input order.

    MSETcpp requires each list to be a strict subset of its background and fails with a
    cryptic ``list_N not subset of its background`` otherwise. Checking here lets the caller
    see *which* genes are at fault (GWC-51 / G3-783).
    """
    universe = {str(g) for g in background}
    seen: set[str] = set()
    out: list[str] = []
    for gene in genes:
        g = str(gene)
        if g not in universe and g not in seen:
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


def _subprocess_runner(binary_path: str) -> MSETRunner:
    """Default runner: write the lists and universes to temp files, then run MSETcpp.

    The universes can be large -- a full gene space is O(100k) identifiers -- so the temp
    directory is removed once the outputs have been read, rather than left behind per run.
    """

    def run(
        g1: list[str],
        g2: list[str],
        bg1: list[str],
        bg2: list[str],
        n_samples: int,
        over: bool,
    ) -> tuple[str, str]:
        workdir = tempfile.mkdtemp(prefix="mset_")
        try:
            paths = {}
            for name, genes in (
                ("group_1.txt", g1),
                ("background_1.txt", bg1),
                ("group_2.txt", g2),
                ("background_2.txt", bg2),
            ):
                path = os.path.join(workdir, name)
                with open(path, "w") as handle:
                    handle.write("\n".join(str(gene) for gene in genes) + "\n")
                paths[name] = path
            cmd = [
                binary_path,
                str(n_samples),
                paths["group_1.txt"],
                paths["background_1.txt"],
                paths["group_2.txt"],
                paths["background_2.txt"],
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
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    return run


class MSET(AbstractTool):
    """Modular Single-set Enrichment Test between two gene lists (wraps the MSET binary)."""

    def __init__(
        self,
        binary_path: str | None = None,
        runner: MSETRunner | None = None,
    ) -> None:
        """Configure how the MSET binary is located/invoked (or inject a runner for tests)."""
        self._binary_path = binary_path or os.environ.get(BINARY_ENV_VAR)
        self._runner = runner

    @property
    def tool_input(self) -> type[MSETInput]:
        """Input schema for the tool."""
        return MSETInput

    @property
    def tool_output(self) -> type[MSETOutput]:
        """Output schema for the tool."""
        return MSETOutput

    @staticmethod
    def _check_backgrounds(tool_input: MSETInput) -> None:
        """Fail early, and legibly, if either list is not a subset of its universe."""
        for label, genes, background in (
            ("group_1", tool_input.group_1_genes, tool_input.group_1_background),
            ("group_2", tool_input.group_2_genes, tool_input.group_2_background),
        ):
            if not background:
                raise ValueError(
                    f"MSET {label}: the background universe is empty. The caller must resolve "
                    "the gene universe and pass it in; MSET reads no background files."
                )
            missing = genes_outside_background(genes, background)
            if not missing:
                continue
            preview = ", ".join(missing[:_MAX_REPORTED_GENES])
            if len(missing) > _MAX_REPORTED_GENES:
                preview += f", and {len(missing) - _MAX_REPORTED_GENES} more"
            raise ValueError(
                f"MSET {label}: {len(missing)} of {len(genes)} genes are outside the supplied "
                f"background universe ({preview}). MSETcpp requires each list to be a subset "
                "of its background. If those are real genes, the universe is too narrow -- it "
                "should be the full gene space for the list's identifier type and species, not "
                "only genes that happen to appear in curated gene sets."
            )

    def _run_binary(self, tool_input: MSETInput) -> tuple[str, str]:
        runner = self._runner
        if runner is None:
            if not self._binary_path:
                raise RuntimeError(
                    f"MSET binary not configured: set {BINARY_ENV_VAR}, or pass "
                    "binary_path/runner."
                )
            runner = _subprocess_runner(self._binary_path)
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
        self._check_backgrounds(tool_input)
        data_text, hist_text = self._run_binary(tool_input)
        return MSETOutput(
            intersect_genes=intersect_genes(tool_input.group_1_genes, tool_input.group_2_genes),
            mset_data=parse_tsv_dict(data_text),
            mset_hist=parse_tsv_dict(hist_text),
        )
