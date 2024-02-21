"""Code for adding homolog/ortholog information from the geneweaver database."""
# ruff: noqa: C901
# TODO: The above noqa is for the complexity of the `add_missing_orthologs` function,
#  which should be refactored to be more readable and maintainable.

import itertools
from typing import List, Optional

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
    aon_schema_name = "public" if aon_schema_name is None else aon_schema_name
    aon_cursor.execute(
        sql.SQL(
            """
        SELECT gn_ref_id FROM {schema}.gn_gene WHERE sp_id in (8,9,10);
        """
        ).format(schema=sql.Identifier(aon_schema_name))
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


def add_missing_orthologs(db: Session, homologs: tuple) -> None:
    """Add missing orthologs to the database.

    :param db: The database session.
    :param homologs: The homologs to add to the database.
    """
    # starting hom_id is the first hom_id of the first homolog,
    # keeps track of current cluster
    curr_hom_id = homologs[0][0]
    # will hold all homolog genes that are not from the new species
    homolog_set = []
    # holds all homolog genes from the new species
    new_species_homologs = []

    for h in homologs:
        # h is in current cluster
        if h[0] == curr_hom_id:
            # check if h is part of the new species
            if h[2] in [6, 10, 11]:
                new_species_homologs.append(h)
            # if h is not in new species, check if the gene is in the agr database.
            #   if it is, add to homolog_set
            else:
                # check if in agr database by getting ode_ref_id, converting that to
                #   gn_ref_id, and searching gn_gene with that agr_ref_id. if all
                #   queries are valid, gene is in agr.
                gw_gene_ref = (
                    db.query(GeneweaverGene)
                    .filter(
                        GeneweaverGene.ode_gene_id == h[1],
                        GeneweaverGene.sp_id == h[2],
                        GeneweaverGene.gdb_id.in_([10, 11, 12, 13, 14, 15, 16]),
                    )
                    .first()
                )
                if gw_gene_ref:
                    agr_ref = ode_ref_to_agr(db, gw_gene_ref.ode_ref_id)
                    gene_in_agr = (
                        db.query(Gene).filter(Gene.gn_ref_id == agr_ref).first()
                    )
                    if gene_in_agr:
                        homolog_set.append(h)

        # h is not in current cluster, new homology set
        #    add new relations from new_species_homologs to rest of homolog_set
        #    reset homolog_set and new_species_homologs
        if h[0] != curr_hom_id:
            orthos = []
            from_agr_genes = {}

            # iterate through new_species_homologs to get the gn_id of each gene
            for n in new_species_homologs:
                n_gw_ref = (
                    db.query(GeneweaverGene)
                    .filter(
                        GeneweaverGene.ode_gene_id == n[1],
                        GeneweaverGene.sp_id == n[2],
                        GeneweaverGene.gdb_id.in_([1, 2, 10]),
                    )
                    .first()
                )
                n_agr_gene = (
                    db.query(Gene).filter(Gene.gn_ref_id == n_gw_ref.ode_ref_id).first()
                )
                from_agr_genes[n[1]] = n_agr_gene.gn_id

            # get permutations of every combination between new_species_homologs and
            #    homolog_set
            pairs = list(itertools.product(new_species_homologs, homolog_set))

            for p in pairs:
                # from gene is first pairs object, to gene is second
                f = p[0]
                t = p[1]

                # get to_gene gn_ref_id
                t_gene_ref = (
                    db.query(GeneweaverGene)
                    .filter(
                        GeneweaverGene.ode_gene_id == t[1],
                        GeneweaverGene.sp_id == t[2],
                        GeneweaverGene.gdb_id.in_([10, 11, 12, 13, 14, 15, 16]),
                    )
                    .first()
                )
                t_agr_ref = ode_ref_to_agr(db, t_gene_ref.ode_ref_id)

                # check that to gene is in agr and geneweaver database
                if not t_gene_ref or not t_agr_ref:
                    continue
                agr_to_gene = db.query(Gene).filter(Gene.gn_ref_id == t_agr_ref).first()
                if not agr_to_gene:
                    continue

                to_gene = agr_to_gene.gn_id
                from_gene = from_agr_genes[f[1]]
                ort_is_best = True
                ort_is_best_revised = True
                ort_is_best_adjusted = True
                ort_num_possible_match_algorithms = 0
                ortho = Ortholog(
                    from_gene=from_gene,
                    to_gene=to_gene,
                    ort_is_best=ort_is_best,
                    ort_is_best_revised=ort_is_best_revised,
                    ort_is_best_is_adjusted=ort_is_best_adjusted,
                    ort_num_possible_match_algorithms=ort_num_possible_match_algorithms,
                    ort_source_name="Homologene",
                )
                orthos.append(ortho)
            db.bulk_save_objects(orthos)
            db.commit()

            # reset homolog_set and new_species_homologs
            homolog_set = []
            new_species_homologs = []

            # add current gene to appropriate list
            if h[2] in [6, 10, 11]:
                new_species_homologs.append(h)
            else:
                homolog_set.append(h)

        # reset curr_hom_id
        curr_hom_id = h[0]
