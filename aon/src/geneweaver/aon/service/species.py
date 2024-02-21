"""Species database queries."""

from typing import List, Optional, Type

from geneweaver.aon.models import GeneweaverSpecies, Species
from sqlalchemy.orm import Session


def get_species(db: Session, name: Optional[str] = None) -> List[Type[Species]]:
    """Get species.

    :param db: The database session.
    :param name: The species name to search for.
    :return: All species that match the queries.
    """
    base_query = db.query(Species)
    if name is not None:
        base_query = base_query.filter(Species.sp_name == name)
    print(str(base_query))
    return base_query.all()


def species_by_id(db: Session, species_id: int) -> Type[Species]:
    """Get species by id.

    :param db: The database session.
    :param species_id: The species id to search for.
    :return: The species info for the provided id.
    """
    return db.query(Species).get(species_id)


def species_by_taxon_id(db: Session, taxon_id: int) -> List[Type[Species]]:
    """Get species by taxon id.

    :param db: The database session.
    :param taxon_id: The taxon id to search for.
    :return: All species that match the queries.
    """
    return db.query(Species).filter(Species.sp_taxon_id == taxon_id).all()


def convert_species_agr_to_ode(db: Session, agr_sp_id: int) -> Optional[int]:
    """Convert the species id from AGR to Geneweaver.

    :param db: The database session.
    :param agr_sp_id: The species id from AGR.
    :return: The species id from Geneweaver.
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
