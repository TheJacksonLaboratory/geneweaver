"""Code for adding missing species information."""
from geneweaver.core import enum
from geneweaver.aon.models import Species
from sqlalchemy.orm import Session


def add_missing_species(db: Session) -> None:
    """Adds three missing species to sp_species table.

    :param db: The database session.
    """
    species_dict = {
        "Gallus gallus": 9031,
        "Canis familiaris": 9615,
        "Macaca mulatta": 9544,
    }
    i = 8
    for s in species_dict.keys():
        species = Species(sp_id=i, sp_name=s, sp_taxon_id=species_dict[s])
        db.add(species)
        i += 1
    db.commit()
