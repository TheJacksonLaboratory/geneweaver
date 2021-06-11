"""create geneweaver tables

Revision ID: 3a8c36f0d3f6
Revises: 60996baf46a6
Create Date: 2021-05-21 01:55:43.720661

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3a8c36f0d3f6'
down_revision = '60996baf46a6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('species',
                    sa.Column('sp_id', sa.Integer(), primary_key=True),
                    sa.Column('sp_name', sa.VARCHAR()),
                    sa.Column('sp_taxid', sa.Integer()),
                    sa.Column('sp_ref_gdb_id', sa.Integer()),
                    sa.Column('sp_date', sa.Date()),
                    sa.Column('sp_biomart_info', sa.VARCHAR()),
                    sa.Column('sp_source_data', sa.Text()),
                    schema='geneweaver'
                    )

    op.create_table('genedb',
                    sa.Column('gdb_id', sa.Integer(), primary_key=True, unique=True),
                    sa.Column('gdb_name', sa.VARCHAR()),
                    sa.Column('sp_id', sa.Integer()),
                    sa.Column('gdb_shortname', sa.VARCHAR()),
                    sa.Column('gdb_date', sa.TIMESTAMP()),
                    sa.Column('gdb_precision', sa.Integer()),
                    sa.Column('gdb_linkout_url', sa.VARCHAR()),
                    sa.ForeignKeyConstraint(['sp_id'], ['geneweaver.species.sp_id'], ),
                    schema='geneweaver'
                    )

    op.create_table('gene',
                    sa.Column('ode_gene_id', sa.BIGINT(), nullable=False),
                    sa.Column('ode_ref_id', sa.VARCHAR(), nullable=False),
                    sa.Column('gdb_id', sa.Integer()),
                    sa.Column('sp_id', sa.Integer()),
                    sa.Column('ode_pref', sa.Boolean()),
                    sa.Column('ode_date', sa.Date()),
                    sa.Column('old_ode_gene_ids', sa.BIGINT()),
                    schema='geneweaver'
                    )
    op.create_primary_key('gene_pkey', 'gene', ['ode_gene_id', 'ode_ref_id'], 'geneweaver')

def downgrade():
    pass
