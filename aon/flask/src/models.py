"""
Database models for our service
"""

from sqlalchemy import Column, String, Integer, Boolean, Table, ForeignKey, VARCHAR, Date, Text, BIGINT, \
    PrimaryKeyConstraint
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


ortholog_algorithms = Table("ortholog_algorithms", Base.metadata,
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


# This format of model allowed for mapping between the algorithm id and orthorithm id. Errors
#    were thrown otherwise. This could be improved upon in the future.
class OrthologAlgorithms(object):
    def __init__(self, algorithm_id, ortholog_id):
        self.algorithm_id = algorithm_id
        self.ortholog_id = ortholog_id


# The following models correspond to datatables in the geneweaver schema that come from the geneweaver database
# Each of these tables are found in a seperate schema geneweaver, so this must be specified in the model.

class Geneweaver_Species(Base):
    __tablename__ = "species"
    __table_args__ = {"schema": "geneweaver"}
    sp_id = Column(Integer, primary_key=True, unique=True)
    sp_name = Column(VARCHAR)
    sp_taxid = Column(Integer)
    sp_ref_gdb_id = Column(Integer)
    sp_date = Column(Date)
    sp_biomart_info = Column(VARCHAR)
    sp_source_data = Column(Text)


class Geneweaver_Gene(Base):
    __tablename__ = "gene"
    ode_gene_id = Column(BIGINT)
    ode_ref_id = Column(VARCHAR)
    gdb_id = Column(Integer)
    sp_id = Column(Integer)
    ode_pref = Column(Boolean)
    ode_date = Column(Date)
    old_ode_gene_ids = Column(BIGINT)
    __table_args__ = (PrimaryKeyConstraint('ode_gene_id', 'ode_ref_id'), {"schema": "geneweaver"})


class Geneweaver_GeneDB(Base):
    __tablename__ = "genedb"
    __table_args__ = {"schema": "geneweaver"}
    gdb_id = Column(Integer, primary_key=True, unique=True)
    gdb_name = Column(VARCHAR)
    sp_id = Column(ForeignKey("species.sp_id"))
    gdb_shortname = Column(VARCHAR)
    gdb_date = Column(Date)
    gdb_precision = Column(Integer)
    gdb_linkout_url = Column(VARCHAR)


# The following model returns information about mouse and human orthologs with their corresponding Ensembl ID
# The column is_mouse_to_human is added to make endpoints more efficent when looking specifically for
#   orthologs from mouse to human or human to mouse.
# The PrimaryKeyConstraint is not present in the table, but it must be added to prevent inaccuracies in running
#   queries.
class Mouse_Human(Base):
    __tablename__ = "mouse_human_map"
    m_id = Column(VARCHAR)
    m_symbol = Column(VARCHAR)
    m_ensembl_id = Column(Integer)
    h_id = Column(VARCHAR)
    h_symbol = Column(VARCHAR)
    h_ensembl_id = Column(Integer)
    is_mouse_to_human = Column(Boolean)
    __table_args__ = (PrimaryKeyConstraint('m_id', 'h_id'),)


mapper(OrthologAlgorithms, ortholog_algorithms)
