"""Convert between Geneweaver and AON ID formats."""
from typing import Optional

from geneweaver.aon.models import (
    GeneweaverGene,
    GeneweaverSpecies,
    Species,
)
from geneweaver.core.enum import GeneIdentifier
from sqlalchemy.orm import Session

# converter functions using first char - these functions improve efficiency and
#    are used here instead of convertODEtoAGR and convertAGRtoGW because they require
#    gdb_id and are used more broadly.


def ode_ref_to_agr(db: Session, ode_ref: str) -> str:
    """Convert a gene reference ID from Geneweaver to AGR format.

    AGR only contains data from some gene data sources Geneweaver has and the format is
    slightly different for the reference ids, so this function adds prefixes to the ids
    where necessary for the AGR format.

    :param db: The database session.
    :param ode_ref: The gene reference ID from Geneweaver.
    :return: The gene reference ID in AGR format.
    """
    ref = ode_ref

    gdb_id = (
        db.query(GeneweaverGene.gdb_id)
        .filter(GeneweaverGene.ode_ref_id == ode_ref)
        .first()
    )
    if gdb_id:
        gdb_id = gdb_id[0]

    gene_id_type = GeneIdentifier(gdb_id)

    if gene_id_type == GeneIdentifier.WORMBASE:
        ref = "WB:" + ode_ref
    elif gene_id_type == GeneIdentifier.SGD:
        ref = "SGD:" + ode_ref
    elif gene_id_type == GeneIdentifier.FLYBASE:
        ref = "FB:" + ode_ref
    elif gene_id_type == GeneIdentifier.ZFIN:
        ref = "ZFIN:" + ode_ref
    elif gene_id_type == GeneIdentifier.RGD:
        ref = ode_ref[:3] + ":" + ode_ref[3:]

    return ref


def agr_ref_to_ode(gn_ref_id: str) -> str:
    """Convert a gene reference ID from AGR to Geneweaver format.

    All gene ref ids in AGR contain the gene source database prefix followed by a colon,
    but geneweaver only has some genes in this format. This function adjusts the ref ids
    to match the geneweaver format.

    :param gn_ref_id: The gene reference ID in AGR format.
    :return: The gene reference ID in Geneweaver format.
    """
    ref = gn_ref_id
    prefix = ref[0 : ref.find(":")]

    # genes with this prefix will have the prefix removed
    gdb_to_remove_prefix = ["WB", "FB", "SGD", "ZFIN"]

    # RGD only requires removing the colon
    if prefix == "RGD":
        ref = ref.replace(":", "")
    elif prefix in gdb_to_remove_prefix:
        ind = ref.find(":") + 1
        ref = ref[ind:]

    # all other gene ref ids will be returned the same if not altered in the above steps
    return ref


def species_ode_to_agr(db: Session, ode_sp_id: int) -> Optional[int]:
    """Convert a species ID from Geneweaver to AGR format.

    :param db: The database session.
    :param ode_sp_id: The species ID from Geneweaver.
    :return: The species ID in AGR format.
    """
    # find the species name, return None if not found in the geneweaver db
    species_name = (
        db.query(GeneweaverSpecies.sp_name)
        .filter(GeneweaverSpecies.sp_id == ode_sp_id)
        .first()
    )
    if species_name:
        species_name = species_name[0]
    else:
        return None
    # get the AGR-normalizer species id from the species name
    agr_sp_id = db.query(Species.sp_id).filter(Species.sp_name == species_name).first()
    if agr_sp_id:
        agr_sp_id = agr_sp_id[0]
    return agr_sp_id


def species_agr_to_ode(db: Session, agr_sp_id: int) -> Optional[int]:
    """Convert a species ID from AGR to Geneweaver format.

    :param db: The database session.
    :param agr_sp_id: The species ID from AGR.
    :return: The species ID in Geneweaver format.
    """
    # find the species name, return None if not found in the AGR-normalizer db
    species_name = db.query(Species.sp_name).filter(Species.sp_id == agr_sp_id).first()
    if species_name:
        species_name = species_name[0]
    else:
        return None
    # get the geneweaver species id
    ode_sp_id = (
        db.query(GeneweaverSpecies.sp_id)
        .filter(GeneweaverSpecies.sp_name == species_name)
        .first()
    )
    if ode_sp_id:
        ode_sp_id = ode_sp_id[0]
    return ode_sp_id
