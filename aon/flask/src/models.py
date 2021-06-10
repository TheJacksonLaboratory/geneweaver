"""
Database models for our service
"""

from sqlalchemy import Column, String, Integer, Boolean, Table, ForeignKey
from sqlalchemy.orm import relationship, mapper
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
                            Column("id", Integer, primary_key=True),
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


class OrthologAlgorithms(object):
    #__table__ == ortholog_algorithms
    #__tablename__ = "ortholog_algorithms"
    #__table_args__ = {'extend_existing': True}
    #id = Column(Integer, primary_key=True)
    #algorithm_id = Column(Integer, ForeignKey("algorithm.id"))
    #ortholog_id = Column(Integer, ForeignKey("ortholog.id"))
    def __init__(self, algorithm_id, ortholog_id):
        self.algorithm_id = algorithm_id
        self.ortholog_id = ortholog_id

mapper(OrthologAlgorithms, ortholog_algorithms)