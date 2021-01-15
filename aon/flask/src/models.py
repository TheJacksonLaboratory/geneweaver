"""
Database models for our service
"""

from sqlalchemy import Column, String, Integer, Boolean, Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Gene(Base):
    __tablename__ = "gene"

    id = Column(Integer, primary_key=True)
    reference_id = Column('ref_id', String, unique=True)
    id_prefix = Column('prefix', String)
    species = Column(ForeignKey("species.id"))


class Species(Base):
    __tablename__ = "species"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    taxon_id = Column(Integer, nullable=False)


ortholog_algorithms = Table("ortholog_algorithms",  Base.metadata,
                            Column("algorithm_id", Integer, ForeignKey("algorithm.id")),
                            Column("ortholog_id", Integer, ForeignKey("ortholog.id")))
    
class Ortholog(Base):
    __tablename__ = "ortholog"
    id = Column(Integer, primary_key=True)
    from_gene = Column(ForeignKey("gene.id"))
    to_gene = Column(ForeignKey("gene.id"))
    is_best = Column(Boolean)
    is_best_revised = Column(Boolean)
    is_best_is_adjusted = Column(Boolean)
    num_possible_match_algorithms = Column(Integer)
    algorithms = relationship("Algorithm",
                              secondary=ortholog_algorithms,
                              backref="orthologs")


class Algorithm(Base):
    __tablename__ = "algorithm"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
