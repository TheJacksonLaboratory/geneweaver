"""
Unit tests for the nightly geneset_search refresh job (G3-826).

`jobs/refresh_search_view.py` is what the
geneweaver-search-view-refresh CronJob runs. It is short, but every one of its
guards exists because the naive version of this job is actively harmful, and
none of them is exercised by deploying it -- a wrong guard shows up as either a
nightly search outage or a silently stale index, months later. So they are
pinned here:

* It must refuse to run when the view has no unique index, and say that
  migration 121 is the fix. The fallback it is refusing -- a plain REFRESH --
  works, and holds ACCESS EXCLUSIVE on the view for the whole rebuild, blocking
  every /api/genesets/search call. Failing loudly is the correct behaviour and
  the easy thing to "fix" by accident.
* It must refresh CONCURRENTLY, and with autocommit on. psycopg2 opens a
  transaction on first execute, and REFRESH ... CONCURRENTLY cannot run inside
  a transaction block, so without autocommit the job fails outright.
* It must not print the DB password. The job logs where it connected, and the
  password is right next to the host in the same secret (CLAUDE.md: never log
  secrets).
* It must bound the refresh with a statement_timeout, so an overrunning rebuild
  is aborted by the database with a reportable error rather than SIGKILLed by
  Kubernetes with none.

Pure unit tests: psycopg2 is faked, so there is no database and no network. The
script is loaded by path because it ships in the image at /app/jobs/ rather than
inside the `src` package.  Run from legacy/:
    python -m unittest tests.test_search_view_refresh
"""
import importlib.util
import io
import pathlib
import sys
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'jobs' / 'refresh_search_view.py'

ENV = {
    'DB_HOST': 'db.example.internal',
    'DB_PORT': '5432',
    'DB_NAME': 'geneweaver',
    'DB_USERNAME': 'gw_user',
    'DB_PASSWORD': 'sup3r-s3cret-p4ssw0rd',
}


def _load_module():
    """Import the job script with a fake psycopg2 in place (no DB, no network)."""
    fake = types.ModuleType('psycopg2')

    def _refuse(*_a, **_k):
        raise AssertionError('psycopg2.connect must be patched in these tests')

    fake.connect = _refuse
    sys.modules['psycopg2'] = fake

    spec = importlib.util.spec_from_file_location('refresh_search_view', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


refresh_search_view = _load_module()


class FakeCursor:
    """Records SQL and answers the three reads the job makes."""

    def __init__(self, unique_indexes, states):
        self._unique_indexes = unique_indexes
        self._states = list(states)
        self._last = ''
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, sql, params=None):
        self._last = sql
        self.executed.append((sql, params))

    def fetchall(self):
        if 'pg_index' in self._last:
            return [(name,) for name in self._unique_indexes]
        raise AssertionError(f'unexpected fetchall for: {self._last}')

    def fetchone(self):
        if 'count(*)' in self._last:
            return self._states.pop(0)
        raise AssertionError(f'unexpected fetchone for: {self._last}')


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.autocommit = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


def run_job(unique_indexes=('geneset_search_gs_id_idx',),
            states=((400_000, 412582), (400_009, 412741)),
            env=None):
    """Run main() against a fake DB. Returns (exit_code, stdout, cursor, connection)."""
    cursor = FakeCursor(unique_indexes, states)
    connection = FakeConnection(cursor)
    out = io.StringIO()
    with patch.dict('os.environ', env if env is not None else ENV, clear=True), \
            patch.object(refresh_search_view.psycopg2, 'connect', return_value=connection), \
            redirect_stdout(out):
        code = refresh_search_view.main()
    return code, out.getvalue(), cursor, connection


class TestUniqueIndexGuard(unittest.TestCase):
    """The job must not fall back to a locking REFRESH."""

    def test_refuses_when_no_unique_index(self):
        with self.assertRaises(SystemExit) as raised:
            run_job(unique_indexes=())
        message = str(raised.exception)
        self.assertIn('121', message, 'the operator must be told which migration to apply')
        self.assertIn('unique index', message.lower())

    def test_refuses_before_refreshing(self):
        """Nothing may be refreshed on the way to that refusal."""
        cursor = FakeCursor((), [])
        connection = FakeConnection(cursor)
        with patch.dict('os.environ', ENV, clear=True), \
                patch.object(refresh_search_view.psycopg2, 'connect', return_value=connection), \
                redirect_stdout(io.StringIO()), \
                self.assertRaises(SystemExit):
            refresh_search_view.main()
        self.assertFalse(
            [sql for sql, _ in cursor.executed if 'REFRESH' in sql],
            'refused runs must not issue a REFRESH',
        )

    def test_proceeds_when_the_index_is_present(self):
        code, _out, cursor, _conn = run_job()
        self.assertEqual(code, 0)
        self.assertTrue([sql for sql, _ in cursor.executed if 'REFRESH' in sql])


class TestRefreshStatement(unittest.TestCase):
    def test_refresh_is_concurrent_and_fully_qualified(self):
        _code, _out, cursor, _conn = run_job()
        refreshes = [sql for sql, _ in cursor.executed if 'REFRESH' in sql]
        self.assertEqual(len(refreshes), 1, 'exactly one refresh per run')
        self.assertEqual(
            refreshes[0],
            'REFRESH MATERIALIZED VIEW CONCURRENTLY production.geneset_search',
        )

    def test_autocommit_is_enabled(self):
        """REFRESH ... CONCURRENTLY cannot run inside a transaction block."""
        _code, _out, _cursor, connection = run_job()
        self.assertTrue(connection.autocommit)

    def test_statement_timeout_is_set_and_parameterised(self):
        _code, _out, cursor, _conn = run_job()
        timeouts = [(sql, params) for sql, params in cursor.executed if 'statement_timeout' in sql]
        self.assertEqual(len(timeouts), 1)
        sql, params = timeouts[0]
        self.assertEqual(params, (refresh_search_view.DEFAULT_STATEMENT_TIMEOUT_MS,))
        self.assertIn('%s', sql, 'the timeout must be bound, not interpolated')

    def test_statement_timeout_is_overridable_from_the_environment(self):
        env = dict(ENV, SEARCH_VIEW_REFRESH_STATEMENT_TIMEOUT_MS='60000')
        _code, _out, cursor, _conn = run_job(env=env)
        timeouts = [params for sql, params in cursor.executed if 'statement_timeout' in sql]
        self.assertEqual(timeouts, [(60000,)])

    def test_timeout_default_is_under_the_cronjob_deadline(self):
        """activeDeadlineSeconds is 3600; the DB must abort first, with a reason."""
        self.assertLess(refresh_search_view.DEFAULT_STATEMENT_TIMEOUT_MS, 3600 * 1000)


class TestSecretsAreNotLogged(unittest.TestCase):
    def test_password_is_absent_from_output(self):
        _code, out, _cursor, _conn = run_job()
        self.assertNotIn(ENV['DB_PASSWORD'], out)

    def test_connection_target_is_logged(self):
        """Non-secret fields are useful and allowed: which database, where, as whom."""
        _code, out, _cursor, _conn = run_job()
        self.assertIn(ENV['DB_HOST'], out)
        self.assertIn(ENV['DB_NAME'], out)
        self.assertIn(ENV['DB_USERNAME'], out)


class TestEnvironmentValidation(unittest.TestCase):
    def test_missing_variables_are_named(self):
        env = {k: v for k, v in ENV.items() if k not in ('DB_HOST', 'DB_PASSWORD')}
        with self.assertRaises(SystemExit) as raised:
            run_job(env=env)
        message = str(raised.exception)
        self.assertIn('DB_HOST', message)
        self.assertIn('DB_PASSWORD', message)

    def test_db_port_defaults_when_absent(self):
        """DB_PORT is not in every environment's secret; 5432 is the sane fallback."""
        env = {k: v for k, v in ENV.items() if k != 'DB_PORT'}
        code, _out, _cursor, _conn = run_job(env=env)
        self.assertEqual(code, 0)


class TestOutcomeReporting(unittest.TestCase):
    def test_reports_the_row_and_watermark_movement(self):
        _code, out, _cursor, _conn = run_job(states=((400_000, 412582), (400_009, 412741)))
        self.assertIn('412582', out)
        self.assertIn('412741', out)
        self.assertIn('+9', out)

    def test_a_shrinking_view_is_not_a_failure(self):
        """Deleted gene sets legitimately drop out of the view."""
        code, _out, _cursor, _conn = run_job(states=((400_000, 412741), (399_990, 412741)))
        self.assertEqual(code, 0)

    def test_an_empty_view_is_a_failure(self):
        code, out, _cursor, _conn = run_job(states=((400_000, 412582), (0, None)))
        self.assertEqual(code, 1)
        self.assertIn('empty', out.lower())


if __name__ == '__main__':
    unittest.main()
