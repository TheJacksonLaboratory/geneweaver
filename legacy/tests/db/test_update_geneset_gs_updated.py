"""
Regression test: update_geneset must bump gs_updated on the save (G3-814).

Raised in review of PR #12. The Sphinx delta index selects on gs_updated
(geneset_delta_src: gs_updated >= the last full-build watermark), but the save path
never wrote that column -- it was set only by update_geneset_date(), which
application.py calls when the edit page is *opened*. So an edit page held open across
the nightly full rebuild produced a save whose gs_updated was older than the
watermark: invisible to every delta, and stale in search until the next full rebuild.

Asserted on the function's own source rather than by calling it: update_geneset runs
permission checks, publication upsert and threshold recomputation against a live
cursor, so exercising it would mean mocking a long chain for a one-column assertion.
What matters is that the column is written in the same UPDATE as the edit -- one
statement, so a save can never land without it -- and that is exactly what the source
shows.
Run from legacy/:  python -m unittest tests.db.test_update_geneset_gs_updated
"""
import inspect
import re
import unittest

from tests.db import _shims

_shims.install()
from src.geneweaverdb import update_geneset  # noqa: E402


class UpdateGenesetGsUpdatedTests(unittest.TestCase):
    def setUp(self):
        self.src = inspect.getsource(update_geneset)

    def _geneset_update_statement(self):
        m = re.search(r'UPDATE geneset\s+SET(.*?)WHERE gs_id', self.src, re.S)
        self.assertIsNotNone(
            m, 'update_geneset no longer contains an "UPDATE geneset SET ... WHERE '
               'gs_id" statement; this test needs rewriting against the new shape')
        return ' '.join(m.group(1).split())

    def test_save_sets_gs_updated(self):
        set_clause = self._geneset_update_statement()
        self.assertIn(
            'gs_updated', set_clause,
            'the geneset UPDATE does not set gs_updated, so an edit is invisible to '
            'the Sphinx delta index until the next nightly full rebuild (G3-814)')

    def test_gs_updated_uses_the_database_clock(self):
        set_clause = self._geneset_update_statement()
        self.assertRegex(
            set_clause, r'gs_updated\s*=\s*NOW\(\)',
            'gs_updated must come from the database clock (NOW()), which is the clock '
            'the watermark it is compared against is also stamped with')

    def test_gs_updated_is_not_a_bound_parameter(self):
        # NOW() is evaluated server-side; passing a client timestamp would reintroduce
        # clock skew between the app pod and the database.
        set_clause = self._geneset_update_statement()
        self.assertNotRegex(set_clause, r'gs_updated\s*=\s*\(?%s')


if __name__ == '__main__':
    unittest.main()
