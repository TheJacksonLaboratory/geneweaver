"""
Database models for our service
"""

from sqlalchemy import Column, String, Integer, Boolean, Table, ForeignKey, VARCHAR, Date, Text, BIGINT, \
    PrimaryKeyConstraint
from sqlalchemy.orm import relationship, mapper
from src.database import BaseAGR, BaseGW

class Gene(BaseAGR):
    __tablename__ = "gn_gene"

    gn_id = Column(Integer, primary_key=True) # id
    gn_ref_id = Column('gn_ref_id', String, unique=True)
    gn_prefix = Column('gn_prefix', String)
    sp_id = Column(ForeignKey("sp_species.sp_id")) # species


class Species(BaseAGR):
    __tablename__ = "sp_species"
    sp_id = Column(Integer, primary_key=True) # id
    sp_name = Column(String, nullable=False) # name
    sp_taxon_id = Column(Integer, nullable=False)


ora_ortholog_algorithms = Table("ora_ortholog_algorithms", BaseAGR.metadata,
                            Column("ora_id", Integer, primary_key=True), # id
                            Column("alg_id", Integer, ForeignKey("alg_algorithm.alg_id")),
                            Column("ort_id", Integer, ForeignKey("ort_ortholog.ort_id")))


class Ortholog(BaseAGR):
    __tablename__ = "ort_ortholog"
    ort_id = Column(Integer, primary_key=True) # id
    from_gene = Column(ForeignKey("gn_gene.gn_id"))
    to_gene = Column(ForeignKey("gn_gene.gn_id"))
    ort_is_best = Column(Boolean)
    ort_is_best_revised = Column(Boolean)
    ort_is_best_is_adjusted = Column(Boolean)
    ort_num_possible_match_algorithms = Column(Integer)
    algorithms = relationship("Algorithm",
                              secondary=ora_ortholog_algorithms,
                              backref="orthologs")


class Algorithm(BaseAGR):
    __tablename__ = "alg_algorithm"
    alg_id = Column(Integer, primary_key=True) # id
    alg_name = Column(String, unique=True) # name


# This format of model allowed for mapping between the algorithm id and orthorithm id. Errors
#    were thrown otherwise. This could be improved upon in the future.
class OrthologAlgorithms(object):
    def __init__(self, alg_id, ort_id):
        self.alg_id = alg_id
        self.ort_id = ort_id


# The following models correspond to datatables in the geneweaver schema that come from the geneweaver database
# Each of these tables are found in a seperate schema geneweaver, so this must be specified in the model.

class Geneweaver_Species(BaseGW):
    __tablename__ = "species"
    __table_args__ = {"schema": "odestatic"}
    sp_id = Column(Integer, primary_key=True, unique=True)
    sp_name = Column(VARCHAR)
    sp_taxid = Column(Integer)
    sp_ref_gdb_id = Column(Integer)
    sp_date = Column(Date)
    sp_biomart_info = Column(VARCHAR)
    sp_source_data = Column(Text)


class Geneweaver_Gene(BaseGW):
    __tablename__ = "gene"
    ode_gene_id = Column(BIGINT)
    ode_ref_id = Column(VARCHAR)
    gdb_id = Column(Integer)
    sp_id = Column(Integer)
    ode_pref = Column(Boolean)
    ode_date = Column(Date)
    old_ode_gene_ids = Column(BIGINT)
    __table_args__ = (PrimaryKeyConstraint('ode_gene_id', 'ode_ref_id'), {"schema": "extsrc"})
    # __table_args__ = (PrimaryKeyConstraint('ode_gene_id', 'ode_ref_id'), {"schema": "geneweaver"})


class Geneweaver_GeneDB(BaseGW):
    __tablename__ = "genedb"
    __table_args__ = {"schema": "odestatic"}
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
class Mouse_Human(BaseAGR):
    __tablename__ = "mhm_mouse_human_map"
    mhm_m_ref_id = Column(VARCHAR)
    mhm_m_symbol = Column(VARCHAR)
    mhm_m_ensembl_id = Column(Integer)
    mhm_h_ref_id = Column(VARCHAR)
    mhm_h_symbol = Column(VARCHAR)
    mhm_h_ensembl_id = Column(Integer)
    mhm_is_mouse_to_human = Column(Boolean)
    __table_args__ = (PrimaryKeyConstraint('mhm_m_ref_id', 'mhm_h_ref_id'),)


mapper(OrthologAlgorithms, ora_ortholog_algorithms)
