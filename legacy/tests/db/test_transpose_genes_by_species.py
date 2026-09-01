"""
Regression tests for transpose_genes_by_species (G3-815).

When a geneset is created from a tool result, the upload page POSTs the tool's
gene list to /transposeGenesetIDs, which calls transpose_genes_by_species to
resolve those identifiers to preferred Gene Symbols in the chosen species. The
old query resolved ONLY through extsrc.homology (Homologene), so any gene with no
homology row was silently dropped -- even on a same-species "transpose" where
nothing needs transposing (6 of 115 genes lost on the C5 sign-off case).

The fix UNIONs a direct same-species lookup (no homology) with the homology
transposition, so:
  * a gene already in the target species is kept by its own preferred symbol;
  * a gene from another species is still transposed via its homolog.

These pin the SQL shape (both branches present; homology no longer gates the
same-species path) and the plumbing (params, result mapping). Pure unit tests --
no database.
Run from legacy/:  python -m unittest tests.db.test_transpose_genes_by_species
"""
import json
import unittest
from unittest.mock import patch, MagicMock

from tests.db import _shims

_shims.install()
from src.geneweaverdb import transpose_genes_by_species  # noqa: E402


class TransposeGenesBySpeciesTests(unittest.TestCase):
    def setUp(self):
        self.patcher = patch('src.geneweaverdb.PooledCursor')
        mock_pc = self.patcher.start()
        self.cursor = MagicMock()
        self.cursor.fetchall.return_value = []
        mock_pc.return_value.__enter__.return_value = self.cursor

    def tearDown(self):
        self.patcher.stop()

    def _attr(self, genes, newSpecies=1, gene_id_type='ode_gene_id'):
        return {'genes': json.dumps(genes),
                'newSpecies': json.dumps(newSpecies),
                'gene_id_type': gene_id_type}

    def _sql(self):
        return ' '.join(self.cursor.execute.call_args[0][0].lower().split())

    def _params(self):
        return self.cursor.execute.call_args[0][1]

    # --- behaviour ----------------------------------------------------------

    def test_returns_symbols_from_cursor(self):
        self.cursor.fetchall.return_value = [('Cd24a',), ('Abhd1',), ('Sox2ot',)]
        self.assertEqual(
            transpose_genes_by_species(self._attr([246, 15654, 19127])),
            ['Cd24a', 'Abhd1', 'Sox2ot'])

    def test_empty_result_returns_empty_list(self):
        self.cursor.fetchall.return_value = []
        self.assertEqual(transpose_genes_by_species(self._attr([1, 2])), [])

    def test_params_carry_the_gene_list_and_species(self):
        transpose_genes_by_species(self._attr([246, 9459], newSpecies=1))
        params = self._params()
        self.assertEqual(params['genelist'], ('246', '9459'))
        self.assertEqual(params['newSpecies'], 1)

    # --- the regression -----------------------------------------------------

    def test_has_a_direct_same_species_branch_without_homology(self):
        # THE fix: a same-species branch that does NOT go through homology, so genes
        # with no Homologene row are kept. The query must UNION two selects, and at
        # least one of them must not reference homology.
        transpose_genes_by_species(self._attr([246]))
        sql = self._sql()
        self.assertIn(' union ', sql, 'query must union a direct + a homology branch')
        branches = sql.split(' union ')
        self.assertTrue(
            any('homology' not in b for b in branches),
            'no homology-free branch -- same-species genes without a homolog are '
            'still dropped (G3-815): %r' % sql)

    def test_still_has_the_homology_transposition_branch(self):
        # The cross-species path must survive: a gene from another species is still
        # transposed via its Homologene homolog.
        transpose_genes_by_species(self._attr([246]))
        sql = self._sql()
        self.assertIn('homology', sql)
        self.assertIn('homologene', sql)

    def test_gene_id_type_is_whitelisted(self):
        # gene_id_type is interpolated into the SQL (a column name), so an unexpected
        # value must not reach the query verbatim.
        transpose_genes_by_species(self._attr([1], gene_id_type='ode_gene_id; DROP TABLE gene'))
        sql = self._sql()
        self.assertNotIn('drop table', sql)
        # falls back to a known-safe column
        self.assertIn('ode_ref_id', sql)


if __name__ == '__main__':
    unittest.main()
