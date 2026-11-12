"""Code for adding homolog/ortholog information from the geneweaver database."""

import itertools
from typing import List, Optional, Sequence

from geneweaver.aon.load.geneweaver.genes import GW_ONLY_GDB_IDS, GW_ONLY_SPECIES
from geneweaver.aon.models import Gene, GeneweaverGene, Ortholog
from geneweaver.aon.service.convert import ode_ref_to_agr
from psycopg import Cursor, sql
from psycopg.rows import Row
from sqlalchemy.orm import Session


def get_homolog_information(
    aon_cursor: Cursor, geneweaver_cursor: Cursor, aon_schema_name: Optional[str] = None
) -> List[Row]:
    """Get homolog information from the geneweaver database.

    :param aon_cursor: The cursor for the aon database.
    :param geneweaver_cursor: The cursor for the geneweaver database.
    :param aon_schema_name: The name of the aon schema in the aon database.
    :return: A list of rows containing homolog information.
    """
    # get all ode_gene_ids of the genes in the gn_gene table for the 3 missing species
    # (GW_ONLY_SPECIES: macaque, chicken, dog). This selected (8,9,10), worm, yeast
    # and chicken: on dev's GeneWeaver 6,004 homology clusters hold macaque or dog
    # genes but none of 8/9/10, and were never looked at (G3-837).
    aon_schema_name = "public" if aon_schema_name is None else aon_schema_name
    aon_cursor.execute(
        sql.SQL(
            """
        SELECT gn_ref_id FROM {schema}.gn_gene WHERE sp_id = ANY(%(species)s);
        """
        ).format(schema=sql.Identifier(aon_schema_name)),
        {"species": list(GW_ONLY_SPECIES)},
    )
    aon_ref_ids = aon_cursor.fetchall()

    geneweaver_cursor.execute(
        """
        SELECT ode_gene_id FROM extsrc.gene WHERE ode_ref_id = ANY(%(ode_ids)s);
        """,
        {"ode_ids": [str(i[0]) for i in aon_ref_ids]},
    )

    ode_gene_ids = geneweaver_cursor.fetchall()

    gw_genes = [str(i[0]) for i in ode_gene_ids]

    # get hom_id, ode_gene_id, and sp_id from the geneweaver homology table for any
    # homolog that is a member of a cluster that contains a gene in agr and of the
    # 3 missing species, also orders by hom_id to make it easier to parse
    geneweaver_cursor.execute(
        """
              SELECT hom_id, ode_gene_id, sp_id FROM extsrc.homology h1
              WHERE h1.hom_id IN (
                 SELECT hom_id FROM extsrc.homology h2
                 WHERE ode_gene_id = ANY(%(ode_ids)s))
              ORDER BY hom_id;
              """,
        {"ode_ids": gw_genes},
    )
    homologs = geneweaver_cursor.fetchall()

    return homologs


# GeneWeaver identifier types of genes AGR also has (MGI, HGNC, RGD, ZFIN, FB, WB,
# SGD): how a cluster member from an AGR species is found in AGR.
AGR_GDB_IDS = (10, 11, 12, 13, 14, 15, 16)


def _agr_gene_id(db: Session, ode_gene_id: int, sp_id: int) -> Optional[int]:
    """Return the AON gn_id of a GeneWeaver gene from an AGR species, if AGR has it.

    The gene's AGR-type identifier is looked up in GeneWeaver, converted to AGR's
    format, and matched against gn_gene.
    """
    gw_gene_ref = (
        db.query(GeneweaverGene)
        .filter(
            GeneweaverGene.ode_gene_id == ode_gene_id,
            GeneweaverGene.sp_id == sp_id,
            GeneweaverGene.gdb_id.in_(AGR_GDB_IDS),
        )
        .first()
    )
    if not gw_gene_ref:
        return None
    agr_ref = ode_ref_to_agr(db, gw_gene_ref.ode_ref_id, gw_gene_ref.gdb_id)
    if not agr_ref:
        return None
    agr_gene = db.query(Gene).filter(Gene.gn_ref_id == agr_ref).first()
    return agr_gene.gn_id if agr_gene else None


def _gw_only_gene_id(db: Session, ode_gene_id: int, sp_id: int) -> Optional[int]:
    """Return the AON gn_id of a gene from a GeneWeaver-only species.

    Those genes were added by ``add_missing_genes`` under the GW_ONLY_GDB_IDS
    identifier types. The lookup used (1, 2, 10): 10 is MGI, never a chicken id, so
    a chicken gene known only by its CGNC id (20) was not found, and the next line
    dereferenced None and aborted the load (G3-837).
    """
    gw_ref = (
        db.query(GeneweaverGene)
        .filter(
            GeneweaverGene.ode_gene_id == ode_gene_id,
            GeneweaverGene.sp_id == sp_id,
            GeneweaverGene.gdb_id.in_(GW_ONLY_GDB_IDS),
        )
        .first()
    )
    if not gw_ref:
        return None
    gene = db.query(Gene).filter(Gene.gn_ref_id == gw_ref.ode_ref_id).first()
    return gene.gn_id if gene else None


def _add_cluster_orthologs(
    db: Session, new_species_homologs: Sequence[Row], agr_gene_ids: dict
) -> int:
    """Add an ortholog from each GeneWeaver-only gene to each AGR gene of a cluster.

    :param db: The database session.
    :param new_species_homologs: The cluster's rows from GW_ONLY_SPECIES.
    :param agr_gene_ids: The cluster's AGR genes, ``{ode_gene_id: gn_id}``.
    :return: The number of orthologs added.
    """
    from_gene_ids = {}
    for n in new_species_homologs:
        gn_id = _gw_only_gene_id(db, n[1], n[2])
        if gn_id is not None:
            from_gene_ids[n[1]] = gn_id

    orthos = [
        Ortholog(
            from_gene=from_gene,
            to_gene=to_gene,
            ort_is_best=True,
            ort_is_best_revised=True,
            ort_is_best_is_adjusted=True,
            ort_num_possible_match_algorithms=0,
            ort_source_name="Homologene",
        )
        for from_gene, to_gene in itertools.product(
            from_gene_ids.values(), agr_gene_ids.values()
        )
    ]
    if orthos:
        db.bulk_save_objects(orthos)
        db.commit()
    return len(orthos)


def add_missing_orthologs(db: Session, homologs: Sequence[Row]) -> None:
    """Add missing orthologs to the database.

    ``homologs`` are GeneWeaver homology rows ``(hom_id, ode_gene_id, sp_id)``
    ordered by hom_id. For each cluster, every gene from a GeneWeaver-only species
    gets an ortholog to every gene of the cluster that AGR has.

    Each cluster is written when the next one starts, and the last one after the
    loop: it used to be skipped, because only a change of hom_id wrote a cluster
    (G3-837).

    :param db: The database session.
    :param homologs: The homologs to add to the database.
    """
    if not homologs:
        return

    curr_hom_id = homologs[0][0]
    # the cluster's genes from the new species
    new_species_homologs = []
    # the cluster's genes AGR has, {ode_gene_id: gn_id}
    agr_gene_ids = {}

    for hom_id, ode_gene_id, sp_id in homologs:
        if hom_id != curr_hom_id:
            _add_cluster_orthologs(db, new_species_homologs, agr_gene_ids)
            new_species_homologs, agr_gene_ids = [], {}
            curr_hom_id = hom_id

        if sp_id in GW_ONLY_SPECIES:
            new_species_homologs.append((hom_id, ode_gene_id, sp_id))
        else:
            gn_id = _agr_gene_id(db, ode_gene_id, sp_id)
            if gn_id is not None:
                agr_gene_ids[ode_gene_id] = gn_id

    _add_cluster_orthologs(db, new_species_homologs, agr_gene_ids)
