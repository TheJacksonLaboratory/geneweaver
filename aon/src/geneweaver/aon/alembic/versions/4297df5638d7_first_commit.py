"""Creates the shared version.schema_version table.

Revision ID: 4297df5638d7
Revises:
Create Date: 2020-12-16 19:27:45.142317

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4297df5638d7"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(table_name):
    config = op.get_context().config
    engine = sa.engine_from_config(
        config.get_section(config.config_ini_section), prefix="sqlalchemy."
    )
    inspector = sa.engine.reflection.Inspector.from_engine(engine)
    tables = inspector.get_table_names(schema="versions")
    return table_name in tables


def upgrade():
    if not _has_table("schema_version"):
        op.create_table(
            "schema_version",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("schema_name", sa.String, nullable=False),
            sa.Column("agr_version", sa.String, nullable=False),
            sa.Column(
                "date", sa.DateTime, nullable=False, server_default=sa.func.now()
            ),
            sa.Column(
                "load_complete",
                sa.Boolean,
                nullable=False,
                server_default=sa.sql.false(),
            ),
            schema="versions",
        )


def downgrade():
    op.drop_table("schema_version", schema="versions")
