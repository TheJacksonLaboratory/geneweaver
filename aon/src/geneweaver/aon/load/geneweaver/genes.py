from geneweaver.aon.models import Gene, Ortholog, Geneweaver_Gene, Species
from sqlalchemy.orm import Session


def convert_gdb_to_prefix(gdb_id):
    """
    :param: gdb_id - gdb_id from genedb table in geneweaver database, used as key for
            gn_prefix in agr gn_gene table because in agr, each prefix corresponds to
            one genedb
    :return: gn_prefix from gdb_dict corresponding to param gdb_id
    :description: converts gdb_id to gn_prefix to communicate between agr and geneweaver
            databases
    """
    gdb_dict = {
        1: "entrez",
        2: "ensembl",
        3: "ensembl_protein",
        4: "ensembl_transcript",
        5: "unigene",
        7: "symbol",
        8: "unannotated",
        10: "MGI",
        11: "HGNC",
        12: "RGD",
        13: "ZFIN",
        14: "FB",
        15: "WB",
        16: "SGD",
        17: "miRBase",
        20: "CGNC",
        21: "Variant",
    }
    return gdb_dict[int(gdb_id)]


def add_missing_genes(db: Session):
    """
    :description: adds genes from geneweaver gene table for the three missing species.
            parses information from this table to create Gene objects to go into gn_gene
            table in agr.
    """

    # query for a list of geneweaver genes from Gallus gallus (sp_id=10, gdb_id=20),
    #    Canis familiaris(sp_id=11, gdb_id=2), and Macaca mulatta (sp_id=6, gdb_id=1)
    with PooledCursor() as cursor:
        cursor.execute(
            """
        SELECT ode_ref_id, gdb_id, sp_id FROM extsrc.gene WHERE sp_id IN (6,10,11)
        AND gdb_id in (1,2,20);
        """
        )
        gw_genes = cursor.fetchall()

    i = 0
    genes = []
    for g in gw_genes:
        gn_ref_id = g[0]
        gn_prefix = convert_gdb_to_prefix(g[1])
        sp_id = convert_species_ode_to_agr(int(g[2]))

        gene = Gene(gn_ref_id=gn_ref_id, gn_prefix=gn_prefix, sp_id=sp_id)
        genes.append(gene)

        # adds genes to database 1000 at a time
        if i % 1000 == 0 and i != 0:
            db.bulk_save_objects(genes)
            db.commit()
            genes = []
            i = 0
        else:
            i += 1

