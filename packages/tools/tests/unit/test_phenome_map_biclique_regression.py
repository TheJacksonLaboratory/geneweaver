"""Regression tests for G3-804, the biclique label-table defect.

`bigraph_edgelist_in` kept both partitions' labels in the single process-global POSIX
`hsearch` table and ignored `ENTER` failures. Two consequences:

* A label appearing in both partitions resolved to the other partition's index -- in range,
  no crash, silently merging two distinct vertices. Reproduces everywhere.
* Once the table filled, `ENTER` failed silently, the next `FIND` missed, and the label was
  appended one past the end of `_label_v1`. macOS libmalloc detects that and raises SIGTRAP
  (which is how this was first seen); glibc rounds the table to the next prime, gains
  incidental headroom and survives.

These run only where the binary is available -- the image build has its own check, so this
covers a developer with `GENEWEAVER_BICLIQUE_BINARY` set.
"""

import os
import subprocess

import pytest
from geneweaver.tools.phenome_map import PhenomeMap

BINARY = os.environ.get("GENEWEAVER_BICLIQUE_BINARY")

needs_binary = pytest.mark.skipif(
    not (BINARY and os.access(BINARY, os.X_OK)),
    reason="GENEWEAVER_BICLIQUE_BINARY is not set to an executable",
)


def _edge_list(genes: list[str], sets: list[str]) -> str:
    """A complete bipartite graph, whose single maximal biclique is every vertex."""
    edges = [(g, s) for g in genes for s in sets]
    lines = [f"{len(genes)}\t{len(sets)}\t{len(edges)}"]
    lines.extend(f"{g}\t{s}" for g, s in edges)
    return "\n".join(lines) + "\n"


def _run(edge_list: str, tmp_path) -> subprocess.CompletedProcess:
    path = tmp_path / "graph.el"
    path.write_text(edge_list)
    return subprocess.run(
        [BINARY, str(path), "-p"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        env={**os.environ, "MALLOC_CHECK_": "3"},
    )


@needs_binary
def test_labels_shared_between_partitions_stay_distinct(tmp_path) -> None:
    """The defect that reproduces on every platform.

    Genes "300".."302" are also gene-set ids. Before the fix the shared table aliased them
    to the gene-set indices and only 397 of the 400 genes came back.
    """
    genes = [str(i) for i in range(400)]
    sets = ["300", "301", "302"]
    result = _run(_edge_list(genes, sets), tmp_path)

    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    resolved = set(lines[1].split("\t")) - {""}
    assert len(resolved) == 400, (
        f"resolved {len(resolved)} of 400 gene labels; cross-partition aliasing is back"
    )
    assert "300" in resolved


@needs_binary
@pytest.mark.parametrize(("num_genes", "num_sets"), [(400, 6), (2000, 20)])
def test_a_dense_graph_does_not_corrupt_the_heap(num_genes: int, num_sets: int, tmp_path) -> None:
    """Every one of these sizes exited 133 (SIGTRAP) before the fix on macOS."""
    genes = [f"Gene{i:05d}" for i in range(num_genes)]
    sets = [str(1000 + j) for j in range(num_sets)]
    result = _run(_edge_list(genes, sets), tmp_path)

    assert result.returncode == 0, (
        f"exit {result.returncode}"
        + (" (SIGTRAP -- heap corruption)" if result.returncode == 133 else "")
        + f": {result.stderr}"
    )
    resolved = set(result.stdout.splitlines()[1].split("\t")) - {""}
    assert len(resolved) == num_genes


@needs_binary
def test_a_truncated_header_is_refused_rather_than_overflowing(tmp_path) -> None:
    """An understated header must be an error, not a write past the label array.

    The bounds check used to sit *below* the append, so the overflowing write had already
    happened by the time it ran.
    """
    genes = [f"Gene{i:04d}" for i in range(50)]
    sets = ["1", "2"]
    # Claim 10 left vertices while supplying 50.
    edges = [(g, s) for g in genes for s in sets]
    bad = "\n".join([f"10\t2\t{len(edges)}"] + [f"{g}\t{s}" for g, s in edges]) + "\n"
    result = _run(bad, tmp_path)

    assert result.returncode == 1, f"expected a clean exit 1, got {result.returncode}"
    assert "too many left vertex labels" in result.stderr


@needs_binary
def test_phenome_map_runs_against_the_real_binary() -> None:
    """End to end: the tool, not just the binary."""
    tool = PhenomeMap()
    gene_sets = {
        "101": ["Abca1", "Brca2", "Cdk2", "Dmd"],
        "102": ["Abca1", "Brca2", "Cdk2"],
        "103": ["Abca1", "Brca2"],
        "104": ["Abca1", "Egfr"],
    }
    output = tool.run(tool.tool_input(gene_sets=gene_sets, gene_ranks={}))
    nodes = output.model_dump(mode="json")["nodes"]

    assert nodes, "no bicliques returned"
    # Abca1 is the only gene in all four sets, so the root spans all four.
    root = min(nodes, key=lambda node: node["depth"])
    assert sorted(root["genesets"]) == ["101", "102", "103", "104"]
    assert root["genes"] == ["Abca1"]
