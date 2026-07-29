"""
Regression tests for single/large upload gene-list processing.

* GWC-36 / G3-768 & binary uploads -- process_gene_list assigns a value of 1 to
  bare gene symbols (a membership list uploads as value-1 genes, not dropped).
* GWC-42 / G3-772 -- get_default_threshold returns the right default per score
  type (binary -> '1'); score_type_value_warnings parses the processed gene
  string into (ref, value) pairs and delegates domain checks to geneweaverdb.

Pure unit tests: all external deps (geneweaverdb, annotator, psycopg2, requests,
flask, tools) are mocked so no DB is needed.
Run from legacy/:  python -m unittest tests.test_upload_processing
"""
import sys
import unittest
from unittest.mock import MagicMock

for _mod in ('geneweaverdb', 'annotator', 'psycopg2', 'requests', 'flask',
             'tools', 'tools.toolcommon'):
    sys.modules[_mod] = MagicMock()

import src.uploadfiles as uploadfiles


class GetDefaultThresholdTests(unittest.TestCase):
    def test_defaults_per_score_type(self):
        self.assertEqual(uploadfiles.get_default_threshold('1'), '0.05')   # p-value
        self.assertEqual(uploadfiles.get_default_threshold('2'), '0.05')   # q-value
        self.assertEqual(uploadfiles.get_default_threshold('3'), '1')      # binary
        self.assertEqual(uploadfiles.get_default_threshold('4'), '-1,1')   # correlation
        self.assertEqual(uploadfiles.get_default_threshold('5'), '-1000,1000')  # effect

    def test_int_input_and_unknown_default(self):
        self.assertEqual(uploadfiles.get_default_threshold(3), '1')        # accepts int
        self.assertEqual(uploadfiles.get_default_threshold('99'), '0.05')  # unknown -> p-value default


class ProcessGeneListTests(unittest.TestCase):
    def _values(self, out):
        """Return the value column for each non-empty output line."""
        vals = []
        for line in out.split('\n'):
            if not line.strip():
                continue
            parts = line.split('\t')
            vals.append((parts[0].strip(), parts[1].strip()))
        return vals

    def test_bare_genes_default_to_value_one(self):
        # A pure membership list must upload as value-1 genes (not dropped).
        out = uploadfiles.process_gene_list('GENE1\nGENE2\nGENE3')
        self.assertEqual(self._values(out),
                         [('GENE1', '1'), ('GENE2', '1'), ('GENE3', '1')])

    def test_existing_values_are_preserved(self):
        out = uploadfiles.process_gene_list('GENE1\t0.5\nGENE2')
        self.assertEqual(self._values(out), [('GENE1', '0.5'), ('GENE2', '1')])


class ScoreTypeValueWarningsTests(unittest.TestCase):
    def setUp(self):
        uploadfiles.db.score_type_value_warnings = MagicMock(return_value=[])

    def test_parses_pairs_and_delegates(self):
        uploadfiles.score_type_value_warnings('3', 'A\t1\nB\t0\n')
        uploadfiles.db.score_type_value_warnings.assert_called_once()
        stype, pairs = uploadfiles.db.score_type_value_warnings.call_args[0]
        self.assertEqual(stype, 3)                       # coerced to int
        self.assertEqual(pairs, [('A', '1'), ('B', '0')])

    def test_non_numeric_score_type_returns_empty(self):
        self.assertEqual(uploadfiles.score_type_value_warnings('notanint', 'A\t1\n'), [])


if __name__ == '__main__':
    unittest.main()
