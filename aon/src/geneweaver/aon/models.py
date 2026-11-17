"""Database models for our service."""

from geneweaver.aon.core.database import BaseAGR, BaseGW
from sqlalchemy import (
    BIGINT,
    VARCHAR,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.orm import relationship


class Version(BaseAGR):
    """Schema version table."""

    __tablename__ = "schema_version"
    __table_args__ = {"schema": "versions"}

    id = Column(Integer, primary_key=True)
    schema_name = Column(String, nullable=False)
    agr_version = Column(String, nullable=False)
    date = Column(Date, nullable=False, server_default="now()")
    load_complete = Column(Boolean, nullable=False, server_default="false")


class Gene(BaseAGR):
    """Gene table."""

    __tablename__ = "gn_gene"
    gn_id = Column(Integer, primary_key=True)  # id
    gn_ref_id = Column("gn_ref_id", String, unique=True)
    gn_prefix = Column("gn_prefix", String)
    sp_id = Column(ForeignKey("sp_species.sp_id"))  # species


class Species(BaseAGR):
    """Species table."""

    __tablename__ = "sp_species"
    sp_id = Column(Integer, primary_key=True)  # id
    sp_name = Column(String, nullable=False)  # name
    sp_taxon_id = Column(Integer, nullable=False)


class OrthologAlgorithms(BaseAGR):
    """Ortholog algorithms table."""

    __tablename__ = "ora_ortholog_algorithms"
    ora_id = Column(Integer, primary_key=True)
    alg_id = Column(ForeignKey("alg_algorithm.alg_id"))
    ort_id = Column(ForeignKey("ort_ortholog.ort_id"))


class Ortholog(BaseAGR):
    """Ortholog table."""

    __tablename__ = "ort_ortholog"
    ort_id = Column(Integer, primary_key=True)  # id
    from_gene = Column(ForeignKey("gn_gene.gn_id"))
    to_gene = Column(ForeignKey("gn_gene.gn_id"))
    ort_is_best = Column(Boolean)
    ort_is_best_revised = Column(Boolean)
    ort_is_best_is_adjusted = Column(Boolean)
    ort_num_possible_match_algorithms = Column(Integer)
    ort_source_name = Column(VARCHAR)
    algorithms = relationship(
        "Algorithm",
        secondary="ora_ortholog_algorithms",
        backref="orthologs",
        cascade="save-update",
    )


class Algorithm(BaseAGR):
    """Algorithm table."""

    __tablename__ = "alg_algorithm"
    alg_id = Column(Integer, primary_key=True)  # id
    alg_name = Column(String, unique=True)  # name


class Homology(BaseAGR):
    """Homology table."""

    __tablename__ = "hom_homology"
    hom_id = Column(Integer)
    gn_id = Column(ForeignKey("gn_gene.gn_id"))
    sp_id = Column(ForeignKey("sp_species.sp_id"))
    hom_source_name = Column(VARCHAR)
    __table_args__ = (PrimaryKeyConstraint("hom_id", "gn_id"),)


# The following models correspond to tables in the geneweaver database,
# so they are created using BaseGW


class GeneweaverSpecies(BaseGW):
    """Geneweaver species table."""

    __tablename__ = "species"
    __table_args__ = {"schema": "odestatic"}
    sp_id = Column(Integer, primary_key=True, unique=True)
    sp_name = Column(VARCHAR)
    sp_taxid = Column(Integer)
    sp_ref_gdb_id = Column(Integer)
    sp_date = Column(Date)
    sp_biomart_info = Column(VARCHAR)
    sp_source_data = Column(Text)


class GeneweaverGene(BaseGW):
    """Geneweaver gene table."""

    __tablename__ = "gene"
    ode_gene_id = Column(BIGINT)
    ode_ref_id = Column(VARCHAR)
    gdb_id = Column(Integer)
    sp_id = Column(Integer)
    ode_pref = Column(Boolean)
    ode_date = Column(Date)
    old_ode_gene_ids = Column(BIGINT)
    __table_args__ = (
        PrimaryKeyConstraint("ode_gene_id", "ode_ref_id"),
        {"schema": "extsrc"},
    )


class GeneweaverGeneDB(BaseGW):
    """Geneweaver gene database table."""

    __tablename__ = "genedb"
    __table_args__ = {"schema": "odestatic"}
    gdb_id = Column(Integer, primary_key=True, unique=True)
    gdb_name = Column(VARCHAR)
    sp_id = Column(ForeignKey("species.sp_id"))
    gdb_shortname = Column(VARCHAR)
    gdb_date = Column(Date)
    gdb_precision = Column(Integer)
    gdb_linkout_url = Column(VARCHAR)
