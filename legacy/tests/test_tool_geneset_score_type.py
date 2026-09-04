"""
Regression tests for tool-output geneset score-type derivation (G3-809).

`derive_score_type(min_val, max_val)` is the pure half of the fix that replaced
two byte-identical inline blocks in genesetblueprint.create_temp_geneset
(/createtempgeneset) and create_geneset (/creategeneset.html). It maps the
observed value range of a tool-created geneset to (gs_threshold_type,
gs_threshold).

Covered here:
* the 0.25 <= max <= 0.5 band that previously matched no branch and left the
  score type None (so process_thresholds/recompute flagged nothing and the whole
  set read out-of-threshold) is now the P-Value branch;
* the type-1 and type-5 thresholds carry no embedded single quotes (the old
  inline version wrapped them in quotes, which the '%s'-interpolated UPDATE then
  double-quoted into malformed SQL);
* the branch boundaries (binary, correlation, effect) are unchanged.

Pure unit tests: genesetblueprint's heavy imports (geneweaverdb, flask, ...) are
mocked so no DB or app context is needed.
Run from legacy/:  python -m unittest tests.test_tool_geneset_score_type
"""
import sys
import unittest
from unittest.mock import MagicMock

# genesetblueprint imports these at module load (geneweaverdb opens a DB pool;
# flask builds a Blueprint). Mock them so the module imports without a DB or app.
for _mod in ('batch', 'geneweaverdb', 'pubmedsvc', 'annotator',
             'decorators', 'curation_assignments', 'flask'):
    sys.modules[_mod] = MagicMock()

from src import genesetblueprint

derive = genesetblueprint.derive_score_type


class DeriveScoreTypeTests(unittest.TestCase):

    def test_binary_all_ones(self):
        # min == max == 1 -> Binary, matching a membership list.
        self.assertEqual(derive(1, 1), (3, '0.5'))

    def test_correlation_positive_upper_bound(self):
        # min >= 0, max > 0.5 -> Correlation over 0..1.
        self.assertEqual(derive(0.2, 0.8), (4, '0,1'))

    def test_correlation_negative_min(self):
        # min < 0 (but within [-1, 1]) -> Correlation over 0..1.
        self.assertEqual(derive(-0.5, 0.8), (4, '0,1'))

    def test_pvalue_small_upper_bound(self):
        # min >= 0, max < 0.25 -> P-Value with threshold = max.
        self.assertEqual(derive(0.0, 0.1), (1, '0.1'))

    def test_effect_out_of_unit_range(self):
        # outside [-1, 1] -> Effect over the observed min,max.
        self.assertEqual(derive(-2, 5), (5, '-2,5'))

    def test_effect_max_above_one(self):
        self.assertEqual(derive(0.0, 2.0), (5, '0.0,2.0'))

    # ---- the closed None gap: 0.25 <= max <= 0.5, min >= 0 ----

    def test_gap_midrange_is_pvalue_not_none(self):
        # Previously returned (None, None): min >= 0, 0.25 <= max <= 0.5 matched no
        # branch. Now folded into P-Value with threshold = max.
        self.assertEqual(derive(0.0, 0.4), (1, '0.4'))

    def test_gap_equal_min_max_in_band(self):
        self.assertEqual(derive(0.3, 0.3), (1, '0.3'))

    def test_gap_boundary_max_exactly_half(self):
        # max == 0.5 is not > 0.5, so it takes the gap (P-Value) branch.
        self.assertEqual(derive(0.0, 0.5), (1, '0.5'))

    def test_just_above_half_is_correlation(self):
        self.assertEqual(derive(0.1, 0.6), (4, '0,1'))

    def test_score_type_is_never_none(self):
        # No input in a reasonable grid should leave the score type undefined.
        vals = [-3, -2, -1, -0.5, 0, 0.1, 0.24, 0.25, 0.3, 0.5, 0.6, 0.9, 1, 2, 5]
        for lo in vals:
            for hi in vals:
                if hi < lo:
                    continue
                ttype, thresh = derive(lo, hi)
                self.assertIn(ttype, (1, 3, 4, 5), msg=f"min={lo} max={hi}")
                self.assertIsNotNone(thresh)

    def test_thresholds_have_no_embedded_quotes(self):
        # Every branch must return a bare string; the caller supplies SQL quoting
        # via a bound parameter now.
        vals = [-3, -1, -0.5, 0, 0.1, 0.2, 0.3, 0.5, 0.6, 1, 2, 5]
        for lo in vals:
            for hi in vals:
                if hi < lo:
                    continue
                _, thresh = derive(lo, hi)
                self.assertNotIn("'", thresh, msg=f"min={lo} max={hi} -> {thresh!r}")


if __name__ == '__main__':
    unittest.main()
