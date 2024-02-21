"""Code to add genes from geneweaver gene table to agr gn_gene table."""

from geneweaver.aon.models import Gene, Species
from geneweaver.core.enum import GeneIdentifier
from psycopg import Cursor
from sqlalchemy.orm import Session

PREFIX_MAPPING = {
    GeneIdentifier.ENTREZ: "entrez",
    GeneIdentifier.ENSEMBLE_GENE: "ensembl",
    GeneIdentifier.ENSEMBLE_PROTEIN: "ensembl_protein",
    GeneIdentifier.ENSEMBLE_TRANSCRIPT: "ensembl_transcript",
    GeneIdentifier.UNIGENE: "unigene",
    GeneIdentifier.GENE_SYMBOL: "symbol",
    GeneIdentifier.UNANNOTATED: "unannotated",
    GeneIdentifier.MGI: "MGI",
    GeneIdentifier.HGNC: "HGNC",
    GeneIdentifier.RGD: "RGD",
    GeneIdentifier.ZFIN: "ZFIN",
    GeneIdentifier.FLYBASE: "FB",
    GeneIdentifier.WORMBASE: "WB",
    GeneIdentifier.SGD: "SGD",
    GeneIdentifier.MIRBASE: "miRBase",
    GeneIdentifier.CGNC: "CGNC",
}


def convert_gdb_to_prefix(gdb_id: int) -> str:
    """Convert gdb_id to gn_prefix.

    :param: gdb_id - gdb_id from genedb table in geneweaver database, used as key for
            gn_prefix in agr gn_gene table because in agr, each prefix corresponds to
            one genedb
    :return: gn_prefix from gdb_dict corresponding to param gdb_id
    :description: converts gdb_id to gn_prefix to communicate between agr and geneweaver
            databases
    """
    try:
        gw_identifier = GeneIdentifier(gdb_id)
    except ValueError:
        return "Variant"

    return PREFIX_MAPPING[gw_identifier]


def get_species_to_taxon_id_map(db: Session) -> dict:
    """Get the species to taxon id map.

    :param db: database session
    :return: species to taxon id map
    """
    species = db.query(Species).all()
    return {s.name: s.sp_id for s in species}


def add_missing_genes(db: Session, geneweaver_cursor: Cursor) -> None:
    """Add genes from geneweaver that weren't loaded from AGR.

    Adds genes from geneweaver gene table for the three missing species.
    parses information from this table to create Gene objects to go into gn_gene
    table in agr.

    :param db: database session
    :param geneweaver_cursor: cursor for geneweaver database
    """
    # query for a list of geneweaver genes from Gallus gallus (sp_id=10, gdb_id=20),
    #    Canis familiaris(sp_id=11, gdb_id=2), and Macaca mulatta (sp_id=6, gdb_id=1)
    print("querying")
    geneweaver_cursor.execute(
        """
    SELECT ode_ref_id, gdb_id, sp_id FROM extsrc.gene WHERE sp_id IN (6,10,11)
    AND gdb_id in (1,2,20);
    """
    )
    gw_genes = geneweaver_cursor.fetchall()
    print("converting")
    genes = []
    for g in gw_genes:
        gn_ref_id = g[0]
        gn_prefix = convert_gdb_to_prefix(g[1])
        sp_id = int(g[2])

        gene = Gene(gn_ref_id=gn_ref_id, gn_prefix=gn_prefix, sp_id=sp_id)
        genes.append(gene)

    print("adding")
    db.add_all(genes)
    print("committing")
    db.commit()
