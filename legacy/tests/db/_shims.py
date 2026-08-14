"""
Import shims so `src.geneweaverdb` can be imported with no database and no
psycopg2 installed.

geneweaverdb builds a ThreadedConnectionPool at module import (minconn=5), so it
cannot simply be imported in a unit test: it would try to connect. We install a
fake psycopg2 whose pool base class is a real class with a no-op __init__, plus
MagicMocks for everything else the module imports at load time. Tests then patch
`src.geneweaverdb.PooledCursor` to feed canned rows.

Call install() BEFORE importing anything from src.geneweaverdb.

(tests/db/test_get_genesets_hom_ids.py carries its own copy of this logic,
written before this helper existed. It is left as-is deliberately -- it is a
passing test on a release branch -- but it could fold into this module later.)
"""
import sys
import types
from unittest.mock import MagicMock


def install():
    """Make `import src.geneweaverdb` succeed with no DB / no psycopg2."""
    psycopg2 = types.ModuleType('psycopg2')
    psycopg2.Error = type('Error', (Exception,), {})
    psycopg2.sql = MagicMock()

    extras = types.ModuleType('psycopg2.extras')
    extras.execute_values = MagicMock()

    pool = types.ModuleType('psycopg2.pool')

    class _NoConnectPool:
        """Real class (geneweaverdb subclasses it) that never opens a socket."""

        def __init__(self, *a, **k):
            pass

        def getconn(self, *a, **k):
            raise AssertionError('PooledCursor must be patched in these tests')

        def putconn(self, *a, **k):
            pass

    pool.ThreadedConnectionPool = _NoConnectPool
    psycopg2.extras = extras
    psycopg2.pool = pool

    sys.modules['psycopg2'] = psycopg2
    sys.modules['psycopg2.extras'] = extras
    sys.modules['psycopg2.pool'] = pool

    # Everything else geneweaverdb pulls in at module load.
    for name in ('config', 'notifications', 'pubmedsvc', 'annotator',
                 'curation_assignments', 'flask', 'tools', 'tools.toolcommon'):
        sys.modules.setdefault(name, MagicMock())
