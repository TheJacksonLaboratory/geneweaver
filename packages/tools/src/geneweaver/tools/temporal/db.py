"""Database access for the tool worker.

The tools themselves take no database connection and never will -- that purity is what makes
them testable and what lets the API run them in-process. But *something* has to turn "the
gene universe for mouse" into 100,000 identifiers, and sending those through Temporal on
every run is what kept MSET off AsyncTask (G3-784): two universes inline measure 1.8-2.7 MiB
against a 2 MiB message limit.

So the activity resolves them here instead, from a reference a few bytes long. The activity
is already the impure boundary -- it loads entry points and shells out to binaries -- and it
runs in GeneWeaver's own worker image, which the in-AsyncTask arrangement could not have
reached a database from.

Connection settings use the same variable names as the API (`DB_HOST`, `DB_PORT`, `DB_NAME`,
`DB_USERNAME`, `DB_PASSWORD`) so one Secret serves both, per the repository rule that
infrastructure comes from the environment rather than being compiled in.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from psycopg import Cursor

#: Read once per connection rather than cached at import, so a restarted pod picks up a
#: rotated password without a rebuild.
REQUIRED_SETTINGS = ("DB_HOST", "DB_NAME", "DB_USERNAME", "DB_PASSWORD")

DEFAULT_PORT = 5432


class DatabaseNotConfigured(RuntimeError):
    """Raised when a tool needs the database but the worker has no connection settings."""


def connection_info() -> str:
    """Build a libpq connection string from the environment.

    :raises DatabaseNotConfigured: If a required setting is missing, naming the ones that
        are, so the failure is fixable from the message alone.
    """
    missing = [name for name in REQUIRED_SETTINGS if not os.environ.get(name)]
    if missing:
        raise DatabaseNotConfigured(
            f"This tool resolves its input from the database, but {', '.join(missing)} "
            f"{'is' if len(missing) == 1 else 'are'} not set. The tool worker needs the same "
            "database settings as the API."
        )
    port = os.environ.get("DB_PORT") or DEFAULT_PORT
    # Password is passed as a parameter, never interpolated into a logged string.
    return (
        f"host={os.environ['DB_HOST']} port={port} dbname={os.environ['DB_NAME']} "
        f"user={os.environ['DB_USERNAME']} password={os.environ['DB_PASSWORD']}"
    )


@contextmanager
def cursor() -> Iterator["Cursor"]:
    """A short-lived read cursor, opened and closed around one resolution.

    Not a pool: an activity resolves its input once, at the start of a run that then spends
    minutes in a binary. Holding a pooled connection across that would tie up a connection
    slot for the whole run.

    :raises DatabaseNotConfigured: If the worker has no database settings.
    """
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as error:  # pragma: no cover - depends on the installed extra
        raise DatabaseNotConfigured(
            "psycopg is not installed. Install geneweaver-tools with the 'db' extra to run "
            "tools that resolve their input from the database."
        ) from error

    with psycopg.connect(connection_info(), row_factory=dict_row) as connection:
        # Read-only: these resolvers answer questions, they never write.
        connection.read_only = True
        with connection.cursor() as open_cursor:
            yield open_cursor
