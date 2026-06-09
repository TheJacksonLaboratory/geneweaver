"""Tests for the Boolean Algebra tool (ported from the legacy CS_Boolean service)."""

from geneweaver.tools.boolean_algebra import (
    BooleanAlgebra,
    BooleanAlgebraInput,
    BooleanAlgebraOutput,
)
from geneweaver.tools.framework.abstract import AbstractTool

# Homolog rows: [hom_source_id, ode_gene_id, ode_ref_id, sp_id, gs_id, gs_abbreviation]
# Two species (1, 2), three gene sets (10, 11, 12).
# - hom 100: shared across gs 10 & 11 (intersection)
# - hom 200: shared across gs 10, 11 & 12 (size-3 intersection)
# - hom 300: only in gs 12 (except)
HOMOLOGS = [
    [100, 1, "A", 1, 10, "GS10"],
    [100, 2, "a", 2, 11, "GS11"],
    [200, 3, "B", 1, 10, "GS10"],
    [200, 4, "b", 2, 11, "GS11"],
    [200, 5, "b2", 1, 12, "GS12"],
    [300, 6, "C", 2, 12, "GS12"],
]
SPECIES = [1, 2]
GENESETS = [10, 11, 12]


def _tool() -> BooleanAlgebra:
    return BooleanAlgebra()


def test_is_abstract_tool() -> None:
    """BooleanAlgebra implements the framework contract."""
    t = _tool()
    assert isinstance(t, AbstractTool)
    assert t.tool_input is BooleanAlgebraInput
    assert t.tool_output is BooleanAlgebraOutput
    assert t.tool_name == "BooleanAlgebra"


def test_union_groups_homologs() -> None:
    """Union groups rows by homology key and reports all gene sets / species."""
    out = _tool().run(
        BooleanAlgebraInput(
            relation="union", geneset_ids=GENESETS, species_ids=SPECIES, homolog_data=HOMOLOGS
        )
    )
    assert isinstance(out, BooleanAlgebraOutput)
    assert out.relation == "Union"
    assert out.num_genesets == 3
    assert out.num_species == 2
    assert set(out.geneset_ids) == {10, 11, 12}
    # three homology groups: 100, 200, 300
    assert set(out.bool_results.keys()) == {100, 200, 300}
    # union does not compute intersect/except
    assert out.intersect_results is None
    assert out.bool_except is None
    # circle groups present (<= 10 gene sets)
    assert out.circle_groups is not None


def test_intersection_buckets_by_size() -> None:
    """Intersection keeps groups with >= at_least gene sets, bucketed by size."""
    out = _tool().run(
        BooleanAlgebraInput(
            relation="intersection",
            at_least=2,
            geneset_ids=GENESETS,
            species_ids=SPECIES,
            homolog_data=HOMOLOGS,
        )
    )
    assert out.intersect_results is not None
    # hom 100 spans 2 gene sets, hom 200 spans 3; hom 300 (single) is excluded
    sizes = out.intersect_results
    assert 2 in sizes and 100 in sizes[2]
    assert 3 in sizes and 200 in sizes[3]
    assert all(300 not in groups for groups in sizes.values())


def test_except_isolates_single_geneset_groups() -> None:
    """Except surfaces groups present in only one gene set."""
    out = _tool().run(
        BooleanAlgebraInput(
            relation="except",
            geneset_ids=GENESETS,
            species_ids=SPECIES,
            homolog_data=HOMOLOGS,
        )
    )
    assert out.bool_except is not None
    # hom 300 (only gs 12) must appear somewhere in the except result
    keys_present = {k for groups in out.bool_except.values() for k in groups}
    assert 300 in keys_present


def test_cluster_reports_per_species() -> None:
    """Cluster output has an entry per species with the expected buckets."""
    out = _tool().run(
        BooleanAlgebraInput(
            relation="union", geneset_ids=GENESETS, species_ids=SPECIES, homolog_data=HOMOLOGS
        )
    )
    assert set(out.bool_cluster.keys()) == {1, 2}
    for sp in SPECIES:
        assert set(out.bool_cluster[sp].keys()) == {"unique", "intersection", "species"}
