"""add id column

Revision ID: bc972ff277e3
Revises: 4297df5638d7
Create Date: 2021-04-10 17:16:32.692859

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bc972ff277e3'
down_revision = '4297df5638d7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ortholog_algorithms',
                    sa.Column('id', sa.Integer(), primary_key=True),
                    sa.Column('algorithm_id', sa.Integer(), nullable=True),
                    sa.Column('ortholog_id', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(['algorithm_id'], ['algorithm.id'], ),
                    sa.ForeignKeyConstraint(['ortholog_id'], ['ortholog.id'], )
                    )


def downgrade():
    pass
