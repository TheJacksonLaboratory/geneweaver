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
* The guard must test the index SHAPE, not just uniqueness. Postgres accepts
  CONCURRENTLY only with a unique index that is immediate and "uses only column
  names and includes all rows", so an expression or partial unique index would
  satisfy a naive indisunique/indisvalid check and then fail the refresh anyway
  -- reporting the index instead of the missing migration, which is exactly what
  the guard exists to prevent. psycopg2 is faked here, so these tests pin the
  catalog predicates in the query rather than evaluating them: the filtering IS
  the SQL, and asserting its text is what catches a predicate being dropped.
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
    fake.Error = type('Error', (Exception,), {})
    sys.modules['psycopg2'] = fake

    spec = importlib.util.spec_from_file_location('refresh_search_view', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


refresh_search_view = _load_module()


class FakeCursor:
    """Records SQL and answers the three reads the job makes."""

    def __init__(self, unique_indexes, states, bloat=((28508, '1890 MB'), (0, '1890 MB')),
                 vacuum_error=None, vacuum_advances=True):
        self._unique_indexes = unique_indexes
        self._states = list(states)
        self._bloat = list(bloat)
        self._vacuum_error = vacuum_error
        # A VACUUM on a relation the caller does not own warns and skips instead of raising, so
        # last_vacuum not advancing is the only signal. False simulates that.
        self._vacuum_advances = vacuum_advances
        self._vacuumed = False
        self._last = ''
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, sql, params=None):
        self._last = sql
        self.executed.append((sql, params))
        if 'VACUUM' in sql:
            if self._vacuum_error is not None:
                raise self._vacuum_error
            self._vacuumed = True

    def fetchall(self):
        if 'pg_index' in self._last:
            return [(name,) for name in self._unique_indexes]
        raise AssertionError(f'unexpected fetchall for: {self._last}')

    def fetchone(self):
        if 'count(*)' in self._last:
            return self._states.pop(0)
        if 'n_dead_tup' in self._last:
            return self._bloat.pop(0) if self._bloat else (0, '0 bytes')
        if 'last_vacuum' in self._last:
            advanced = self._vacuumed and self._vacuum_advances
            return ('2026-09-17T14:00:00Z' if advanced else None,)
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
            env=None, bloat=((28508, '1890 MB'), (0, '1890 MB')), vacuum_error=None,
            vacuum_advances=True):
    """Run main() against a fake DB. Returns (exit_code, stdout, cursor, connection)."""
    cursor = FakeCursor(unique_indexes, states, bloat=bloat, vacuum_error=vacuum_error,
                        vacuum_advances=vacuum_advances)
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

    def test_guard_requires_an_index_shape_refresh_can_actually_use(self):
        """Unique and valid is not the requirement; Postgres asks for three things more."""
        _code, _out, cursor, _conn = run_job()
        catalog = [(sql, params) for sql, params in cursor.executed if 'pg_index' in sql]
        self.assertEqual(len(catalog), 1, 'the catalog is consulted exactly once')
        query, params = catalog[0]
        for predicate, why in (
            ('x.indisunique', 'CONCURRENTLY needs a unique index'),
            ('x.indisvalid', 'a failed CREATE INDEX leaves an invalid one behind'),
            ('x.indimmediate', 'a non-immediate index is not accepted'),
            ('x.indpred IS NULL', 'a partial index does not include all rows'),
            ('x.indexprs IS NULL', 'an expression index does not use only column names'),
        ):
            self.assertIn(predicate, query, f'guard must require {predicate}: {why}')
        self.assertEqual(
            params,
            (refresh_search_view.VIEW_SCHEMA, refresh_search_view.VIEW_NAME),
            'schema and view must be bound, not interpolated',
        )

    def test_refusal_names_the_shape_requirement(self):
        """So an operator who has a partial unique index is not told to re-apply 121 blindly."""
        with self.assertRaises(SystemExit) as raised:
            run_job(unique_indexes=())
        message = str(raised.exception)
        self.assertIn('CONCURRENTLY', message)
        for word in ('immediate', 'plain columns', 'WHERE clause'):
            self.assertIn(word, message)


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
        """Two now: the session-wide one, then the VACUUM's own deadline-bounded one."""
        _code, _out, cursor, _conn = run_job()
        timeouts = [(sql, params) for sql, params in cursor.executed if 'statement_timeout' in sql]
        self.assertEqual(len(timeouts), 2)
        sql, params = timeouts[0]
        self.assertEqual(params, (refresh_search_view.DEFAULT_STATEMENT_TIMEOUT_MS,))
        self.assertIn('%s', sql, 'the timeout must be bound, not interpolated')
        self.assertIn('%s', timeouts[1][0])

    def test_statement_timeout_is_overridable_from_the_environment(self):
        env = dict(ENV, SEARCH_VIEW_REFRESH_STATEMENT_TIMEOUT_MS='60000')
        _code, _out, cursor, _conn = run_job(env=env)
        timeouts = [params for sql, params in cursor.executed if 'statement_timeout' in sql]
        self.assertEqual(timeouts[0], (60000,), 'the session timeout honours the override')

    def test_statement_timeout_cannot_be_disabled(self):
        """Postgres treats zero as no timeout, which would let Kubernetes kill the pod first."""
        for value in ('0', '-1'):
            with self.subTest(value=value), self.assertRaises(SystemExit) as raised:
                run_job(env=dict(ENV, SEARCH_VIEW_REFRESH_STATEMENT_TIMEOUT_MS=value))
            self.assertIn('must be from 1 through', str(raised.exception))

    def test_statement_timeout_override_preserves_the_deadline_margin(self):
        """Overrides may not consume the five-minute gap below activeDeadlineSeconds."""
        for value in (
            str(refresh_search_view.MAX_STATEMENT_TIMEOUT_MS + 1),
            str(3600 * 1000),
        ):
            with self.subTest(value=value), self.assertRaises(SystemExit) as raised:
                run_job(env=dict(ENV, SEARCH_VIEW_REFRESH_STATEMENT_TIMEOUT_MS=value))
            self.assertIn('CronJob deadline', str(raised.exception))

    def test_statement_timeout_override_must_be_an_integer(self):
        """A malformed override must fail clearly before opening a database connection."""
        with self.assertRaises(SystemExit) as raised:
            run_job(env=dict(ENV, SEARCH_VIEW_REFRESH_STATEMENT_TIMEOUT_MS='55 minutes'))
        self.assertIn('must be an integer', str(raised.exception))

    def test_maximum_statement_timeout_is_accepted(self):
        """The largest override that preserves the five-minute margin remains valid."""
        env = dict(
            ENV,
            SEARCH_VIEW_REFRESH_STATEMENT_TIMEOUT_MS=str(
                refresh_search_view.MAX_STATEMENT_TIMEOUT_MS
            ),
        )
        _code, _out, cursor, _conn = run_job(env=env)
        timeouts = [params for sql, params in cursor.executed if 'statement_timeout' in sql]
        # timeouts[1] is the VACUUM's own deadline-bounded budget, asserted separately.
        self.assertEqual(timeouts[0], (refresh_search_view.MAX_STATEMENT_TIMEOUT_MS,))

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


class TestVacuumAfterRefresh(unittest.TestCase):
    """CONCURRENTLY buys its lock-free rebuild with dead tuples; this job owns the cleanup.

    Autovacuum's trigger is 50 + 0.2 * live_tuples -- ~53,000 rows on Prod -- and a nightly delta
    produces far fewer, so the table can bloat for months without tripping it. Measured
    2026-09-16: Prod last autovacuumed 2026-04-15 with 28,508 dead tuples; dev never at all.
    """

    def test_vacuums_after_refreshing(self):
        _code, _out, cursor, _conn = run_job()
        order = [i for i, (sql, _) in enumerate(cursor.executed)
                 if 'REFRESH' in sql or 'VACUUM' in sql]
        kinds = ['REFRESH' if 'REFRESH' in cursor.executed[i][0] else 'VACUUM' for i in order]
        self.assertEqual(kinds, ['REFRESH', 'VACUUM'], 'vacuum must follow the refresh, once each')

    def test_vacuum_statement_shape(self):
        _code, _out, cursor, _conn = run_job()
        vacuums = [sql for sql, _ in cursor.executed if 'VACUUM' in sql]
        self.assertEqual(vacuums, ['VACUUM (ANALYZE) production.geneset_search'])
        self.assertNotIn('FULL', vacuums[0],
                         'VACUUM FULL takes ACCESS EXCLUSIVE and belongs in a maintenance window')

    def test_bloat_is_reported_either_side(self):
        """The condition the vacuum exists to prevent stays visible even on a clean run."""
        _code, out, _cursor, _conn = run_job(bloat=((28508, '1890 MB'), (0, '1287 MB')))
        self.assertIn('28508 dead tuples', out)
        self.assertIn('1890 MB', out)
        self.assertIn('1287 MB', out)

    def test_a_failed_vacuum_does_not_fail_the_job(self):
        """The refresh has already committed, so search is fresh; retrying it would be worse."""
        err = refresh_search_view.psycopg2.Error('out of shared memory')
        code, out, cursor, _conn = run_job(vacuum_error=err)
        self.assertEqual(code, 0, 'a vacuum failure must not trigger backoffLimit retries')
        self.assertIn('WARNING', out)
        self.assertIn('refresh SUCCEEDED', out,
                      'the operator must not read this as a stale-search failure')
        self.assertTrue([sql for sql, _ in cursor.executed if 'REFRESH' in sql])

    def test_a_silently_skipped_vacuum_is_reported(self):
        """PostgreSQL warns and skips rather than raising when the caller is not the owner.

        On PG 15 -- what these instances run -- ownership is the only route; the MAINTAIN
        privilege that would let a non-owner vacuum arrived in 16. So a role change would turn
        this step into a no-op that still logs success. last_vacuum is the only ground truth.
        """
        code, out, cursor, _conn = run_job(vacuum_advances=False)
        self.assertEqual(code, 0, 'still not a job failure -- the refresh succeeded')
        self.assertIn('WARNING', out)
        self.assertIn('last_vacuum did not advance', out)
        self.assertIn('owned by this job', out, 'the warning must name the likely cause')
        self.assertTrue([sql for sql, _ in cursor.executed if 'VACUUM' in sql])

    def test_a_confirmed_vacuum_reports_the_new_watermark(self):
        _code, out, _cursor, _conn = run_job()
        self.assertIn('vacuumed in', out)
        self.assertIn('last_vacuum now', out)
        self.assertNotIn('did not advance', out)

    def test_vacuum_is_bounded_by_what_is_left_of_the_job_deadline(self):
        """statement_timeout is PER STATEMENT, so without this the VACUUM would get a fresh 55
        minutes on top of whatever the refresh spent -- up to 110 against a 60-minute pod
        deadline."""
        _code, out, cursor, _conn = run_job()
        timeouts = [params[0] for sql, params in cursor.executed if 'statement_timeout' in sql]
        self.assertEqual(len(timeouts), 2, 'the vacuum sets its own')
        budget_ms = timeouts[1]
        ceiling_ms = (refresh_search_view.DEFAULT_JOB_DEADLINE_SECONDS
                      - refresh_search_view.VACUUM_DEADLINE_MARGIN_SECONDS) * 1000
        self.assertLessEqual(budget_ms, ceiling_ms,
                             'the vacuum may never be given more than the deadline minus margin')
        self.assertIn('vacuum budget:', out)

    def test_vacuum_is_skipped_when_the_deadline_is_nearly_spent(self):
        """Better to skip cleanup than to have the pod killed mid-statement.

        A pod killed on activeDeadlineSeconds marks the Job Failed/DeadlineExceeded, which would
        report a COMPLETED refresh as a failure and never print the "refresh SUCCEEDED" line.
        (It would not repeat the refresh -- verified on the dev cluster, k8s 1.34, that
        activeDeadlineSeconds takes precedence over backoffLimit and the Job goes terminal with
        zero replacement pods.)
        """
        env = dict(ENV, SEARCH_VIEW_REFRESH_JOB_DEADLINE_SECONDS='100')
        code, out, cursor, _conn = run_job(env=env)
        self.assertEqual(code, 0, 'skipping cleanup is not a job failure')
        self.assertFalse([sql for sql, _ in cursor.executed if 'VACUUM' in sql],
                         'no VACUUM may be issued when there is no budget for it')
        self.assertIn('skipping the VACUUM', out)
        self.assertIn('refresh SUCCEEDED', out)

    def test_the_job_deadline_comes_from_the_environment(self):
        """The manifest's activeDeadlineSeconds is the single source of truth and is injected."""
        env = dict(ENV, SEARCH_VIEW_REFRESH_JOB_DEADLINE_SECONDS='600')
        _code, _out, cursor, _conn = run_job(env=env)
        budget_ms = [params[0] for sql, params in cursor.executed if 'statement_timeout' in sql][1]
        ceiling_ms = (600 - refresh_search_view.VACUUM_DEADLINE_MARGIN_SECONDS) * 1000
        self.assertLessEqual(budget_ms, ceiling_ms)

    def test_no_vacuum_when_the_view_came_back_empty(self):
        """That path returns 1; cleaning up after a broken refresh is not the priority."""
        code, _out, cursor, _conn = run_job(states=((400_000, 412582), (0, None)))
        self.assertEqual(code, 1)
        self.assertFalse([sql for sql, _ in cursor.executed if 'VACUUM' in sql])

    def test_no_vacuum_when_the_guard_refuses(self):
        cursor = FakeCursor((), [])
        connection = FakeConnection(cursor)
        with patch.dict('os.environ', ENV, clear=True), \
                patch.object(refresh_search_view.psycopg2, 'connect', return_value=connection), \
                redirect_stdout(io.StringIO()), \
                self.assertRaises(SystemExit):
            refresh_search_view.main()
        self.assertFalse([sql for sql, _ in cursor.executed if 'VACUUM' in sql])


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
