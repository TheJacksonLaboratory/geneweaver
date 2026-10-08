"""Unit tests for the tool-input resolvers' homology and pairwise-deletion queries."""

from unittest.mock import MagicMock

import pytest
from geneweaver.db import tool_input


def _cursor(*results: list) -> MagicMock:
    """A cursor returning each result list from successive ``fetchall`` calls."""
    cursor = MagicMock()
    cursor.fetchall.side_effect = list(results)
    return cursor


class TestCollapseHomologs:
    """Legacy "Homology: Included": homologous genes become one member across the run."""

    def test_orthologs_across_species_become_one_shared_member(self) -> None:
        """A mouse and a human set overlap on their orthologs, under one label."""
        members = [(1, 10, "Drd2"), (1, 11, "Th"), (2, 20, "DRD2")]
        homology = [(10, 500), (20, 500)]
        assert tool_input.collapse_homologs(members, homology, [1, 2]) == {
            "1": ["DRD2/Drd2", "Th"],
            "2": ["DRD2/Drd2"],
        }

    def test_a_gene_with_no_homolog_keeps_its_symbol(self) -> None:
        """Without homology rows the result is the plain symbol membership."""
        members = [(1, 10, "Drd2"), (2, 11, "Th")]
        assert tool_input.collapse_homologs(members, [], [1, 2]) == {
            "1": ["Drd2"],
            "2": ["Th"],
        }

    def test_groups_chain_transitively(self) -> None:
        """A gene in two groups joins both, so all three genes merge."""
        members = [(1, 10, "A"), (2, 20, "B"), (3, 30, "C")]
        homology = [(10, 1), (20, 1), (20, 2), (30, 2)]
        merged = tool_input.collapse_homologs(members, homology, [1, 2, 3])
        assert merged == {"1": ["A/B/C"], "2": ["A/B/C"], "3": ["A/B/C"]}

    def test_paralogs_in_one_set_count_once(self) -> None:
        """Two homologous genes in the same set are one member, as in legacy's matrix."""
        members = [(1, 10, "Hba-a1"), (1, 11, "Hba-a2")]
        homology = [(10, 7), (11, 7)]
        assert tool_input.collapse_homologs(members, homology, [1]) == {"1": ["Hba-a1/Hba-a2"]}

    def test_homology_rows_for_absent_genes_are_ignored(self) -> None:
        """A group member outside the run does not appear in any label."""
        members = [(1, 10, "Drd2")]
        assert tool_input.collapse_homologs(members, [(99, 500), (10, 500)], [1]) == {
            "1": ["Drd2"]
        }

    def test_every_requested_geneset_has_an_entry_in_order(self) -> None:
        """An empty set keeps its position; positions are part of the tools' contract."""
        merged = tool_input.collapse_homologs([(2, 10, "x")], [], [3, 2])
        assert list(merged) == ["3", "2"]
        assert merged["3"] == []


class TestHomologousGeneSymbols:
    """The query wrapper, under both row factories the codebase uses."""

    def test_tuple_rows(self) -> None:
        """Tuple rows, as packages/db's own connections return."""
        cursor = _cursor([(1, 10, "Drd2"), (2, 20, "DRD2")], [(10, 500), (20, 500)])
        merged = tool_input.homologous_gene_symbols_by_geneset(cursor, [1, 2])
        assert merged == {"1": ["DRD2/Drd2"], "2": ["DRD2/Drd2"]}

    def test_dict_rows(self) -> None:
        """dict rows, as the API's pool returns."""
        cursor = _cursor(
            [
                {"gs_id": 1, "ode_gene_id": 10, "ode_ref_id": "Drd2"},
                {"gs_id": 2, "ode_gene_id": 20, "ode_ref_id": "DRD2"},
            ],
            [{"ode_gene_id": 10, "hom_id": 500}, {"ode_gene_id": 20, "hom_id": 500}],
        )
        merged = tool_input.homologous_gene_symbols_by_geneset(cursor, [1, 2])
        assert merged == {"1": ["DRD2/Drd2"], "2": ["DRD2/Drd2"]}

    def test_ids_bind_as_parameters(self) -> None:
        """Gene set and gene ids are bound, never formatted into the SQL."""
        cursor = _cursor([(1, 10, "Drd2")], [])
        tool_input.homologous_gene_symbols_by_geneset(cursor, [1])
        (members_sql, members_params), (hom_sql, hom_params) = (
            call.args for call in cursor.execute.call_args_list
        )
        assert members_params == {"geneset_ids": [1]}
        assert "ANY(%(geneset_ids)s)" in members_sql
        assert hom_params == {"gene_ids": [10]}
        assert "extsrc.homology" in hom_sql

    def test_no_genesets_runs_no_query(self) -> None:
        """Nothing asked, nothing queried."""
        cursor = _cursor()
        assert tool_input.homologous_gene_symbols_by_geneset(cursor, []) == {}
        cursor.execute.assert_not_called()


class TestPlatformQueries:
    """What pairwise deletion reads: each set's platform, and a platform's genes."""

    @pytest.mark.parametrize(
        "rows",
        [
            [(753, 1, 8), (1026, 1, -7)],
            [
                {"gs_id": 753, "sp_id": 1, "gs_gene_id_type": 8},
                {"gs_id": 1026, "sp_id": 1, "gs_gene_id_type": -7},
            ],
        ],
    )
    def test_geneset_platforms(self, rows) -> None:
        """``{gs_id: (sp_id, gs_gene_id_type)}`` under either row factory."""
        cursor = _cursor(rows)
        assert tool_input.geneset_platforms(cursor, [753, 1026]) == {
            753: (1, 8),
            1026: (1, -7),
        }

    def test_platform_genes_match_the_platform_or_its_set(self) -> None:
        """Legacy's ``m.pf_id = %s OR m.pf_set = %s``, bound once as a parameter."""
        cursor = _cursor([("Drd2",), ("Th",), (None,)])
        assert tool_input.platform_gene_symbols(cursor, 71) == {"Drd2", "Th"}
        sql, params = cursor.execute.call_args.args
        assert params == {"platform_id": 71}
        assert "m.pf_id = %(platform_id)s OR m.pf_set = %(platform_id)s" in sql
