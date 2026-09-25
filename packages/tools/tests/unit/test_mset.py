"""Tests for the MSET tool (wraps the MSET C++ binary via an injectable runner)."""

import pathlib
import subprocess
import types

import pytest
from geneweaver.tools.framework.abstract import AbstractTool
from geneweaver.tools.mset import (
    MSET,
    MSETInput,
    MSETOutput,
    genes_outside_background,
    intersect_genes,
    parse_tsv_dict,
)
from geneweaver.tools.mset.tool import _subprocess_runner


def test_is_abstract_tool() -> None:
    """MSET implements the framework contract."""
    t = MSET(runner=lambda *a: ("", ""))
    assert isinstance(t, AbstractTool)
    assert t.tool_input is MSETInput
    assert t.tool_output is MSETOutput
    assert t.tool_name == "MSET"


def test_intersect_genes_order_and_dedup() -> None:
    """Intersection preserves group-1 order and deduplicates."""
    assert intersect_genes(["a", "b", "c", "b"], ["b", "c", "x"]) == ["b", "c"]


def test_parse_tsv_dict() -> None:
    """TSV key/value lines parse into a dict; blank lines ignored."""
    assert parse_tsv_dict("p_value\t0.01\nmean\t5\n\n") == {"p_value": "0.01", "mean": "5"}


def test_genes_outside_background_finds_missing_in_order() -> None:
    """Out-of-universe genes come back deduplicated, in input order."""
    assert genes_outside_background(["a", "x", "b", "x", "y"], ["a", "b"]) == ["x", "y"]


def test_genes_outside_background_empty_when_subset() -> None:
    """A subset yields nothing."""
    assert genes_outside_background(["a", "b"], ["a", "b", "c"]) == []


def test_run_invokes_runner_and_parses() -> None:
    """run() passes the right args to the runner and parses both outputs."""
    captured = {}

    def fake_runner(g1, g2, bg1, bg2, n, over):
        captured["args"] = (g1, g2, bg1, bg2, n, over)
        return "p_value\t0.02\n", "0\t10\n1\t5\n"

    out = MSET(runner=fake_runner).run(
        MSETInput(
            group_1_genes=["a", "b"],
            group_2_genes=["b", "c"],
            group_1_background=["a", "b", "z"],
            group_2_background=["b", "c", "q"],
            number_of_samples=500,
            over_representation=True,
        )
    )
    assert isinstance(out, MSETOutput)
    # group_2 correctly uses its own background (legacy bug fixed), and both backgrounds
    # arrive as resolved gene universes rather than file names.
    assert captured["args"] == (
        ["a", "b"],
        ["b", "c"],
        ["a", "b", "z"],
        ["b", "c", "q"],
        500,
        True,
    )
    assert out.intersect_genes == ["b"]
    assert out.mset_data == {"p_value": "0.02"}
    assert out.mset_hist == {"0": "10", "1": "5"}


def test_empty_background_raises_before_the_binary() -> None:
    """An unresolved universe fails with an actionable message, not a cryptic binary error."""
    with pytest.raises(ValueError, match="background universe is empty"):
        MSET(runner=lambda *a: ("", "")).run(
            MSETInput(
                group_1_genes=["a"],
                group_2_genes=["a"],
                group_1_background=[],
                group_2_background=["a"],
            )
        )


def test_genes_outside_background_raises_and_names_them() -> None:
    """The subset precondition is checked here, naming the offending genes (GWC-51)."""
    with pytest.raises(ValueError, match=r"group_2: 2 of 3 genes are outside"):
        MSET(runner=lambda *a: ("", "")).run(
            MSETInput(
                group_1_genes=["a"],
                group_2_genes=["a", "LINC02853", "NRIR"],
                group_1_background=["a"],
                group_2_background=["a"],
            )
        )


def test_out_of_background_error_truncates_long_lists() -> None:
    """Many offenders are summarised rather than dumped in full."""
    missing = [f"GENE{i}" for i in range(25)]
    with pytest.raises(ValueError, match="and 15 more"):
        MSET(runner=lambda *a: ("", "")).run(
            MSETInput(
                group_1_genes=missing,
                group_2_genes=["a"],
                group_1_background=["a"],
                group_2_background=["a"],
            )
        )


def test_subset_check_runs_before_the_runner() -> None:
    """A bad universe must not reach the binary at all."""
    called = False

    def runner(*_args):
        nonlocal called
        called = True
        return "", ""

    with pytest.raises(ValueError):
        MSET(runner=runner).run(
            MSETInput(
                group_1_genes=["x"],
                group_2_genes=["a"],
                group_1_background=["a"],
                group_2_background=["a"],
            )
        )
    assert called is False


def test_unconfigured_binary_raises() -> None:
    """Without a runner or binary path, running raises a helpful error."""
    with pytest.raises(RuntimeError, match="MSET binary not configured"):
        MSET().run(
            MSETInput(
                group_1_genes=["a"],
                group_2_genes=["a"],
                group_1_background=["a"],
                group_2_background=["a"],
            )
        )


def test_default_runner_materialises_the_universes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The universes are written from the input, not read from a background directory."""
    seen: dict = {}

    def fake_run(cmd, cwd, capture_output, text, check):
        seen["cmd"] = cmd
        seen["files"] = {
            pathlib.Path(p).name: pathlib.Path(p).read_text().split() for p in cmd[2:6]
        }
        pathlib.Path(cwd, "mset_output.tsv").write_text("p_value\t0.03\n")
        pathlib.Path(cwd, "mset_hist.tsv").write_text("0\t2\n")
        return types.SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    data, hist = _subprocess_runner("/nonexistent/MSETcpp")(
        ["a", "b"], ["b"], ["a", "b", "z"], ["b", "q"], 250, False
    )

    assert data == "p_value\t0.03\n"
    assert hist == "0\t2\n"
    # Argument order the binary expects: n, list1, bg1, list2, bg2, mode.
    assert seen["cmd"][1] == "250"
    assert seen["cmd"][-1] == "-U"
    assert seen["files"]["group_1.txt"] == ["a", "b"]
    assert seen["files"]["background_1.txt"] == ["a", "b", "z"]
    assert seen["files"]["group_2.txt"] == ["b"]
    assert seen["files"]["background_2.txt"] == ["b", "q"]


def test_default_runner_cleans_up_its_temp_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """Large universes must not accumulate on disk across runs."""
    workdirs: list[str] = []

    def fake_run(cmd, cwd, capture_output, text, check):
        workdirs.append(cwd)
        pathlib.Path(cwd, "mset_output.tsv").write_text("k\tv\n")
        pathlib.Path(cwd, "mset_hist.tsv").write_text("k\tv\n")
        return types.SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    _subprocess_runner("/nonexistent/MSETcpp")(["a"], ["a"], ["a"], ["a"], 10, True)

    assert workdirs and not pathlib.Path(workdirs[0]).exists()
