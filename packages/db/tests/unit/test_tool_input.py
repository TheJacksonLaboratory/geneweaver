"""Unit tests for the tool-input resolvers' homology and pairwise-deletion queries."""

from typing import ClassVar
from unittest.mock import MagicMock

import pytest
from geneweaver.db import tool_input
from geneweaver.db.query.membership import Thresholds


def _text(sql) -> str:
    """A query as text, whether a plain string or composed SQL."""
    return sql if isinstance(sql, str) else " ".join(sql.as_string(None).split())


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
        assert "ANY(%(geneset_ids)s)" in _text(members_sql)
        assert hom_params == {"gene_ids": [10]}
        assert "extsrc.homology" in hom_sql

    def test_no_genesets_runs_no_query(self) -> None:
        """Nothing asked, nothing queried."""
        cursor = _cursor()
        assert tool_input.homologous_gene_symbols_by_geneset(cursor, []) == {}
        cursor.execute.assert_not_called()


class TestHomologAnnotations:
    """BooleanAlgebra's input: one row per gene in each set, as legacy's query gave."""

    def test_one_row_per_gene_by_its_preferred_symbol(self) -> None:
        """``ode_pref`` alone admits a gene's preferred UniGene id too (G3-830).

        BooleanAlgebra counts rows, so two identifiers for one gene in one set counted as
        two sets; legacy's ``gdb_id = 7`` is what keeps it to one.
        """
        cursor = _cursor([])
        tool_input.homolog_annotations(cursor, [1, 2], [1])
        sql, params = cursor.execute.call_args.args
        assert "g.gdb_id = 7" in _text(sql)
        assert "g.ode_pref = TRUE" in _text(sql)
        assert params == {"geneset_ids": [1, 2], "species_ids": [1]}


class TestThresholdChoice:
    """Every membership query takes the run's threshold choice (curation, 2026-10-16)."""

    RESOLVERS: ClassVar[list] = [
        (lambda c, t: tool_input.gene_symbols_by_geneset(c, [1], t), [[]]),
        (lambda c, t: tool_input.homologous_gene_symbols_by_geneset(c, [1], t), [[], []]),
        (lambda c, t: tool_input.membership_rows(c, [1], t), [[]]),
        (lambda c, t: tool_input.homology_pairs(c, [1], t), [[]]),
        (lambda c, t: tool_input.homolog_annotations(c, [1], [1], t), [[]]),
    ]
    IDS: ClassVar[list[str]] = [
        "symbols",
        "homologous",
        "membership_rows",
        "homology_pairs",
        "annotations",
    ]

    @pytest.mark.parametrize(("call", "results"), RESOLVERS, ids=IDS)
    def test_every_gene_by_default_and_the_stored_flag_never_read(self, call, results) -> None:
        """A gene set is not inherently thresholded: no choice, every gene."""
        cursor = _cursor(*results)
        call(cursor, Thresholds())
        sql = _text(cursor.execute.call_args_list[0].args[0])
        assert "gsv_in_threshold" not in sql
        assert "TRUE" in sql

    @pytest.mark.parametrize(("call", "results"), RESOLVERS, ids=IDS)
    def test_custom_cutoffs_reach_every_membership_filter(self, call, results) -> None:
        """Each filter in the query is the run's, its cutoffs bound, never formatted in."""
        cursor = _cursor(*results)
        call(cursor, Thresholds("custom", p_value=0.01))
        sql, params = cursor.execute.call_args_list[0].args
        sql = _text(sql)
        assert params["t_p_value"] == 0.01
        assert "0.01" not in sql
        assert sql.count("<= %(t_p_value)s") == sql.count("production.geneset gs") >= 1

    def test_uploader_reads_the_stored_cutoff(self) -> None:
        """The one-click choice re-reads the stored cutoff with <=."""
        cursor = _cursor([])
        tool_input.gene_symbols_by_geneset(cursor, [1], Thresholds("uploader"))
        sql = _text(cursor.execute.call_args.args[0])
        assert "gv.gsv_value <= gs.gs_threshold::numeric" in sql


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


class TestSpeciesByGeneset:
    """MSET's species: both gene sets must share one, so the caller looks it up first."""

    @pytest.mark.parametrize(
        "rows",
        [
            [(407805, 2), (218676, 2)],
            [{"gs_id": 407805, "sp_id": 2}, {"gs_id": 218676, "sp_id": 2}],
        ],
    )
    def test_maps_each_found_set_to_its_species(self, rows) -> None:
        """``{gs_id: sp_id}`` under either row factory, the ids bound as a parameter."""
        cursor = _cursor(rows)
        assert tool_input.species_by_geneset(cursor, [407805, 218676, 9]) == {
            407805: 2,
            218676: 2,
        }
        sql, params = cursor.execute.call_args.args
        assert params == {"geneset_ids": [407805, 218676, 9]}
        assert "gs_id = ANY(%(geneset_ids)s)" in sql

    def test_no_genesets_runs_no_query(self) -> None:
        """Nothing to look up is an empty answer, not a query."""
        cursor = _cursor()
        assert tool_input.species_by_geneset(cursor, []) == {}
        cursor.execute.assert_not_called()


class TestGeneUniverse:
    """MSET's background: the species' full gene space, never the curated subset (G3-784)."""

    @pytest.mark.parametrize(
        "rows", [[("Drd2",), ("Th",)], [{"ode_ref_id": "Drd2"}, {"ode_ref_id": "Th"}]]
    )
    def test_returns_the_symbols_under_either_row_factory(self, rows) -> None:
        """One identifier per row, in the query's order."""
        assert tool_input.gene_universe(_cursor(rows), 1) == ["Drd2", "Th"]

    def test_every_preferred_gene_of_the_species_not_only_curated_ones(self) -> None:
        """Species comes from the gene itself; no gene set or curation tier is consulted.

        Legacy derived the background from genes in Tier I-III gene sets, so a gene unique
        to a Tier-IV set sat outside its own universe (GWC-51 / G3-783).
        """
        cursor = _cursor([("Drd2",)])
        tool_input.gene_universe(cursor, 2)
        sql, params = cursor.execute.call_args.args
        text = " ".join(sql.split())
        assert params == {"species_id": 2, "gene_id_type": 7}
        assert "FROM extsrc.gene WHERE sp_id = %(species_id)s" in text
        assert "gdb_id = %(gene_id_type)s" in text
        assert "ode_pref = 't'" in text
        assert "DISTINCT" in text
        for curated_only in ("geneset", "cur_id", "gs_id"):
            assert curated_only not in text

    def test_another_identifier_space_when_asked(self) -> None:
        """The member lists and the universe must share one identifier space."""
        cursor = _cursor([])
        tool_input.gene_universe(cursor, 1, gene_id_type=2)
        assert cursor.execute.call_args.args[1] == {"species_id": 1, "gene_id_type": 2}

    def test_a_null_identifier_is_not_a_gene(self) -> None:
        """A NULL would otherwise reach MSETcpp's background file as the text "None"."""
        assert tool_input.gene_universe(_cursor([("Drd2",), (None,)]), 1) == ["Drd2"]


class TestGenesetLabels:
    """Combine's column headers."""

    @pytest.mark.parametrize(
        "rows",
        [
            [(5, "Dopamine set", "DA")],
            [{"gs_id": 5, "gs_name": "Dopamine set", "gs_abbreviation": "DA"}],
        ],
    )
    def test_id_name_and_abbreviation_per_set(self, rows) -> None:
        """``[gs_id, gs_name, gs_abbreviation]`` rows, the ids bound as a parameter."""
        cursor = _cursor(rows)
        assert tool_input.geneset_labels(cursor, [5]) == [[5, "Dopamine set", "DA"]]
        assert cursor.execute.call_args.args[1] == {"geneset_ids": [5]}


class TestJaccardDistributions:
    """JaccardSimilarity's null distributions, one per size pair and homology choice."""

    @pytest.mark.parametrize(
        "rows",
        [
            [(10, 20, False, 0.0, 900), (10, 20, False, 0.1, 100), (10, 20, True, 0.0, 5)],
            [
                {
                    "set_size1": 10,
                    "set_size2": 20,
                    "homology": False,
                    "jaccard_coef": 0.0,
                    "frequency": 900,
                },
                {
                    "set_size1": 10,
                    "set_size2": 20,
                    "homology": False,
                    "jaccard_coef": 0.1,
                    "frequency": 100,
                },
                {
                    "set_size1": 10,
                    "set_size2": 20,
                    "homology": True,
                    "jaccard_coef": 0.0,
                    "frequency": 5,
                },
            ],
        ],
    )
    def test_rows_group_into_one_distribution_per_key(self, rows) -> None:
        """Rows for the same ``(set_size1, set_size2, homology)`` form one distribution."""
        assert tool_input.jaccard_distributions(_cursor(rows)) == [
            {
                "set_size1": 10,
                "set_size2": 20,
                "homology": False,
                "frequencies": [(0.0, 900), (0.1, 100)],
            },
            {"set_size1": 10, "set_size2": 20, "homology": True, "frequencies": [(0.0, 5)]},
        ]

    def test_reads_the_extsrc_table(self) -> None:
        """Schema-qualified: dev also has an ``extsrc_20240918`` copy of this table."""
        cursor = _cursor([])
        assert tool_input.jaccard_distributions(cursor) == []
        assert "FROM extsrc.jaccard_distribution_results" in cursor.execute.call_args.args[0]
