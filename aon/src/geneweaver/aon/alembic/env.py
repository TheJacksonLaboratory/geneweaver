from logging.config import fileConfig

from sqlalchemy import engine_from_config, text
from sqlalchemy import pool

from alembic import context

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = [Base.metadata]

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    _config_section = config.get_section(config.config_ini_section)
    x_arguments = context.get_x_argument(as_dictionary=True)

    current_tenant = x_arguments.get("tenant")
    dburi = x_arguments.get('dburi')
    if dburi:
        _config_section['sqlalchemy.url'] = dburi

    connectable = engine_from_config(
        _config_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        connection.execute(text('CREATE SCHEMA IF NOT EXISTS "%s"' % 'versions'))
        connection.execute(text('CREATE SCHEMA IF NOT EXISTS "%s"' % current_tenant))
        connection.execute(text('set search_path to "%s"' % current_tenant))
        connection.commit()
        connection.dialect.default_schema_name = current_tenant

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # include_schemas=False,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
