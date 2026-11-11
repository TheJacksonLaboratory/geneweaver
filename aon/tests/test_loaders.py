"""Test the AON data loaders (G3-837)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from geneweaver.aon.cli import load as cli_load
from geneweaver.aon.load.agr import load as agr_load
from geneweaver.aon.load.geneweaver import genes as gw_genes
from geneweaver.aon.load.geneweaver import homologs as gw_homologs
from geneweaver.core import enum


def _clusters(orthologs: list) -> dict:
    """Run add_homology over (from_gene, to_gene) pairs; return {gene: {hom_ids}}."""
    db = MagicMock()
    db.query.return_value = [
        SimpleNamespace(from_gene=f, to_gene=t, ort_source_name="AGR")
        for f, t in orthologs
    ]
    genes = {g for pair in orthologs for g in pair}
    with patch.object(
        agr_load, "get_gene_gn_id_sp_id_map", return_value={g: 1 for g in genes}
    ):
        agr_load.add_homology(db)
    membership = {}
    for call in db.bulk_save_objects.call_args_list:
        for hom in call.args[0]:
            membership.setdefault(hom.gn_id, set()).add(hom.hom_id)
    return membership


def test_a_gene_joins_the_cluster_of_its_ortholog() -> None:
    """Gene 5 joins 1's cluster, so 5's ortholog 6 does too.

    Keyed to curr_hom_id (the newest cluster, 3-4's), 6 landed in 3-4's cluster:
    on dev's v8 load that grew one cluster to 141,102 genes.
    """
    membership = _clusters([(1, 2), (3, 4), (1, 5), (5, 6)])
    assert membership[6] == membership[1] == membership[5]
    assert membership[6] != membership[3]
    assert all(len(hom_ids) == 1 for hom_ids in membership.values())


def _orthologs_added(db: MagicMock) -> list:
    return [
        (o.from_gene, o.to_gene)
        for call in db.bulk_save_objects.call_args_list
        for o in call.args[0]
    ]


def test_the_last_cluster_is_written() -> None:
    """Each cluster's orthologs are added, the last one included.

    Only a change of hom_id wrote a cluster, so the last never was.
    """
    db = MagicMock()
    homologs = [(1, 100, 6), (1, 200, 1), (2, 300, 11), (2, 400, 2)]
    gn_ids = {100: 10, 200: 20, 300: 30, 400: 40}
    with (
        patch.object(
            gw_homologs, "_gw_only_gene_id", side_effect=lambda db, g, sp: gn_ids[g]
        ),
        patch.object(
            gw_homologs, "_agr_gene_id", side_effect=lambda db, g, sp: gn_ids[g]
        ),
    ):
        gw_homologs.add_missing_orthologs(db, homologs)
    assert _orthologs_added(db) == [(10, 20), (30, 40)]


def test_a_gene_missing_from_geneweaver_is_skipped_not_fatal() -> None:
    """A new-species gene with no GeneWeaver id of the loaded types is skipped.

    It was dereferenced as None, aborting the whole load.
    """
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with patch.object(gw_homologs, "_agr_gene_id", return_value=20):
        gw_homologs.add_missing_orthologs(db, [(1, 100, 10), (1, 200, 1)])
    db.bulk_save_objects.assert_not_called()


def test_no_homologs_is_a_no_op() -> None:
    """An empty result no longer raises IndexError on homologs[0]."""
    db = MagicMock()
    gw_homologs.add_missing_orthologs(db, [])
    db.bulk_save_objects.assert_not_called()


def test_the_geneweaver_only_species_are_macaque_chicken_and_dog() -> None:
    """One set, used by every GeneWeaver loader. One query used (8, 9, 10)."""
    assert gw_genes.GW_ONLY_SPECIES == (6, 10, 11)


def test_homolog_information_reads_the_geneweaver_only_species() -> None:
    """The AON gene query selects GW_ONLY_SPECIES, bound, not (8, 9, 10)."""
    aon_cursor, gw_cursor = MagicMock(), MagicMock()
    aon_cursor.fetchall.return_value = []
    gw_cursor.fetchall.return_value = []
    gw_homologs.get_homolog_information(aon_cursor, gw_cursor, "v1")
    assert aon_cursor.execute.call_args.args[1] == {"species": [6, 10, 11]}


def test_chicken_genes_are_found_by_their_cgnc_id() -> None:
    """The new-species lookup uses the types those genes were loaded under.

    It used gdb_id 10 (MGI) where chicken genes carry 20 (CGNC).
    """
    assert int(enum.GeneIdentifier.CGNC) in gw_genes.GW_ONLY_GDB_IDS
    assert int(enum.GeneIdentifier.MGI) not in gw_genes.GW_ONLY_GDB_IDS


def test_only_a_completed_release_counts_as_loaded() -> None:
    """A failed load's incomplete Version row no longer blocks a retry."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    with patch.object(cli_load, "SessionLocal", return_value=session):
        assert cli_load.agr_release_exists("6.0.0a2") is False
    criteria = session.query.return_value.filter.call_args.args
    assert any("load_complete" in str(c) for c in criteria)


def test_every_geneweaver_species_has_a_taxon_id() -> None:
    """init_species looks up every species but ALL; none may be missing."""
    missing = [
        s
        for s in enum.Species
        if s != enum.Species.ALL and s not in agr_load.TAXON_ID_MAP
    ]
    assert missing == []


def test_ode_ref_to_agr_uses_the_gdb_id_it_is_given() -> None:
    """The loader passes the row's gdb_id, so no second lookup can go wrong."""
    from geneweaver.aon.service.convert import ode_ref_to_agr

    db = MagicMock()
    assert ode_ref_to_agr(db, "FBgn0000744", 14) == "FB:FBgn0000744"
    db.query.assert_not_called()


def test_ode_ref_to_agr_skips_rows_without_a_gdb_id() -> None:
    """The lookup filters out NULL gdb_id rows, and an unknown type is not fatal.

    Dev's extsrc.gene has 34,377 species-0 rows with no gdb_id that repeat real ids;
    landing on one raised TypeError (a 500 from /genes/by-ref-id?ref_id_type=gw).
    """
    from geneweaver.aon.service.convert import ode_ref_to_agr

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    assert ode_ref_to_agr(db, "FBgn0000744") == "FBgn0000744"
    criteria = db.query.return_value.filter.call_args.args
    assert any("IS NOT NULL" in str(c) for c in criteria)

    db.query.return_value.filter.return_value.first.return_value = (14,)
    assert ode_ref_to_agr(db, "FBgn0000744") == "FB:FBgn0000744"
