from typing import Optional

from geneweaver.aon.models import Geneweaver_Species, Species
from sqlalchemy.orm import Session


def get_species(db: Session, name: Optional[str] = None):
    base_query = db.query(Species)
    if name is not None:
        base_query = base_query.filter(Species.sp_name == name)
    return base_query.all()


def species_by_id(db: Session, species_id: int):
    return db.query(Species).get(species_id)


def species_by_taxon_id(db: Session, taxon_id: int):
    return db.query(Species).filter(Species.sp_taxon_id == taxon_id).all()


def geneweaver_id(db: Session, species_id: int):
    return convert_species_agr_to_ode(db, species_id)


def convert_species_agr_to_ode(db: Session, agr_sp_id):
    # find the species name, return None if not found in the AGR-normalizer db
    species_name = db.query(Species.sp_name).filter(Species.sp_id == agr_sp_id).first()
    if species_name:
        species_name = species_name[0]
    else:
        return None
    # get the geneweaver species id
    ode_sp_id = (
        db.query(Geneweaver_Species.sp_id)
        .filter(Geneweaver_Species.sp_name == species_name)
        .first()
    )
    if ode_sp_id:
        ode_sp_id = ode_sp_id[0]
    return ode_sp_id
