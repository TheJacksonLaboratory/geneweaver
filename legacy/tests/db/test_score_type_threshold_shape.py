"""
Regression test: a threshold whose shape does not match the score type must never
reach the write (G3-823).

Found by test T3 of the 1.6.0b SQA verification pass. A curator changing a gene set's
score type from a two-sided type (Correlation/Effect, whose threshold is a "low,high"
pair) to a one-sided one (P-Value/Q-Value, a single number) without also editing the
threshold field got "An unknown error ocurred." and lost the change.

The UPDATE itself is legal -- production.geneset.gs_threshold is character varying, so
"0.0,10.0" stores fine. What fails is the AFTER UPDATE trigger:
geneset_threshold_update_trigger -> process_thresholds, whose type-1/2 branch evaluates
`cast(gs_threshold as numeric)`. The comma raises, the trigger aborts, and the whole
statement rolls back.

normalize_threshold_for_type is the server-side half of the fix (editgenesets.html
reshapes the field client-side, which is what makes the requirement visible). Its
contract is narrow and worth stating: for the one-sided types the value it returns must
always be something `cast(... as numeric)` accepts.

Run from legacy/:  python -m unittest tests.db.test_score_type_threshold_shape
"""
import inspect
import re
import unittest

from tests.db import _shims

_shims.install()
from src.geneweaverdb import (  # noqa: E402
    DEFAULT_ONE_SIDED_THRESHOLD,
    ONE_SIDED_THRESHOLD_TYPES,
    normalize_threshold_for_type,
    update_geneset,
)

P_VALUE, Q_VALUE, BINARY, CORRELATION, EFFECT = 1, 2, 3, 4, 5


class NormalizeThresholdForTypeTests(unittest.TestCase):
    def test_the_reported_case_is_corrected(self):
        # The exact reproduction from G3-823: GS408080 was Effect "0.0,10.0" and was
        # switched to P-Value with the threshold field untouched.
        threshold, warning = normalize_threshold_for_type(P_VALUE, '0.0,10.0')

        self.assertEqual(threshold, '0.05')
        self.assertIsNotNone(
            warning, 'a substituted threshold must be reported, not applied silently')

    def test_a_range_is_corrected_for_both_one_sided_types(self):
        for ttype in ONE_SIDED_THRESHOLD_TYPES:
            for value in ('0.0,10.0', '-1,1', '0.05,0.01'):
                threshold, warning = normalize_threshold_for_type(ttype, value)
                self.assertEqual(threshold, DEFAULT_ONE_SIDED_THRESHOLD,
                                 'type %s / %r' % (ttype, value))
                self.assertIsNotNone(warning, 'type %s / %r' % (ttype, value))

    def test_the_low_end_of_the_range_is_not_reused_as_a_cutoff(self):
        # Taking "0.0" from "0.0,10.0" would cast fine and so fix the crash, but a
        # p-value cutoff of 0 puts every gene out of threshold -- it would turn a
        # visible error into a silently emptied gene set.
        threshold, _ = normalize_threshold_for_type(P_VALUE, '0.0,10.0')
        self.assertNotEqual(threshold, '0.0')
        self.assertNotEqual(threshold, '0.0,10.0')

    def test_a_valid_single_cutoff_is_left_alone(self):
        for value in ('0.05', '0.01', '0', '1', '2.0E-8', '1e-300', '  0.05  '):
            for ttype in ONE_SIDED_THRESHOLD_TYPES:
                threshold, warning = normalize_threshold_for_type(ttype, value)
                self.assertEqual(threshold, value, 'type %s / %r' % (ttype, value))
                self.assertIsNone(warning, 'type %s / %r' % (ttype, value))

    def test_scientific_notation_survives(self):
        # 2.0E-8 is a real SQA threshold (GS219224, the T4 fixture). Rejecting it
        # would silently loosen a published set's cutoff to 0.05.
        threshold, warning = normalize_threshold_for_type(P_VALUE, '2.0E-8')
        self.assertEqual(threshold, '2.0E-8')
        self.assertIsNone(warning)

    def test_two_sided_types_are_never_touched(self):
        # process_thresholds parses these with string_to_array, which does not raise,
        # so there is no crash to prevent and nothing to guess at.
        for ttype in (CORRELATION, EFFECT):
            for value in ('0.0,10.0', '-1,1', '0.05', 'junk', ''):
                threshold, warning = normalize_threshold_for_type(ttype, value)
                self.assertEqual(threshold, value, 'type %s / %r' % (ttype, value))
                self.assertIsNone(warning, 'type %s / %r' % (ttype, value))

    def test_binary_is_never_touched(self):
        # GWC-44: a binary set is a membership list and is not thresholded at all.
        for value in ('1', '0.0,10.0', '', 'anything'):
            threshold, warning = normalize_threshold_for_type(BINARY, value)
            self.assertEqual(threshold, value)
            self.assertIsNone(warning)

    def test_a_missing_threshold_gets_the_default(self):
        for value in ('', None, '   '):
            threshold, warning = normalize_threshold_for_type(P_VALUE, value)
            self.assertEqual(threshold, DEFAULT_ONE_SIDED_THRESHOLD, repr(value))
            self.assertIsNotNone(warning, repr(value))

    def test_non_finite_values_are_corrected(self):
        # float() accepts these but numeric does not (or does not on every server
        # version), which is the same class of failure being fixed.
        for value in ('inf', '-inf', 'nan', 'Infinity', 'NaN'):
            threshold, warning = normalize_threshold_for_type(P_VALUE, value)
            self.assertEqual(threshold, DEFAULT_ONE_SIDED_THRESHOLD, repr(value))
            self.assertIsNotNone(warning, repr(value))

    def test_an_unreadable_score_type_is_left_alone(self):
        # The caller's own int() conversion should surface this, not a silent rewrite.
        for ttype in (None, '', 'abc'):
            threshold, warning = normalize_threshold_for_type(ttype, '0.0,10.0')
            self.assertEqual(threshold, '0.0,10.0', repr(ttype))
            self.assertIsNone(warning, repr(ttype))

    def test_a_string_score_type_is_understood(self):
        # request.form values arrive as strings.
        threshold, warning = normalize_threshold_for_type('1', '0.0,10.0')
        self.assertEqual(threshold, DEFAULT_ONE_SIDED_THRESHOLD)
        self.assertIsNotNone(warning)

    def test_one_sided_results_are_always_castable(self):
        # The contract: whatever goes in, what comes out for a one-sided type is
        # something cast(... as numeric) accepts. This is the assertion that keeps the
        # trigger from ever aborting a save again.
        junk = ['0.0,10.0', '-1,1', '', None, '   ', 'junk', 'inf', 'nan', '0.05',
                '2.0E-8', ',', '1,', ',1', '0.05,', 'P < 0.05', '0.05;DROP', '[]']
        for ttype in ONE_SIDED_THRESHOLD_TYPES:
            for value in junk:
                threshold, _ = normalize_threshold_for_type(ttype, value)
                try:
                    parsed = float(threshold)
                except (TypeError, ValueError):
                    self.fail('type %s / %r produced un-castable %r'
                              % (ttype, value, threshold))
                self.assertFalse(parsed != parsed, 'NaN from %r' % (value,))
                self.assertNotIn(parsed, (float('inf'), float('-inf')),
                                 'infinity from %r' % (value,))

    def test_the_warning_names_the_score_type_and_the_rejected_value(self):
        _, warning = normalize_threshold_for_type(Q_VALUE, '0.0,10.0')
        self.assertIn('Q-Value', warning)
        self.assertIn('0.0,10.0', warning,
                      'the curator needs to see what was discarded')
        self.assertIn(DEFAULT_ONE_SIDED_THRESHOLD, warning,
                      'and what it was replaced with')


class UpdateGenesetCallsTheNormalizerTests(unittest.TestCase):
    """update_geneset runs permission checks, a publication upsert and threshold
    recomputation against a live cursor, so these assert on its source -- the same
    approach tests/db/test_update_geneset_gs_updated.py takes, and for the same
    reason. What matters is ordering: the correction has to happen before the write."""

    def setUp(self):
        self.src = inspect.getsource(update_geneset)

    def test_the_threshold_is_normalized_before_the_update(self):
        call = self.src.find('normalize_threshold_for_type')
        update = self.src.find('UPDATE geneset')

        self.assertNotEqual(call, -1,
                            'update_geneset no longer normalises the threshold shape; '
                            'a two-sided threshold under a one-sided type aborts the '
                            'save in the AFTER UPDATE trigger (G3-823)')
        self.assertNotEqual(update, -1,
                            'update_geneset no longer contains "UPDATE geneset"; this '
                            'test needs rewriting against the new shape')
        self.assertLess(call, update,
                        'the threshold must be corrected before the UPDATE -- '
                        'afterwards the trigger has already aborted the statement')

    def test_the_normalized_threshold_is_what_gets_stored(self):
        # Re-binding gs_threshold is what carries the correction into both the UPDATE
        # and the recompute call below it.
        self.assertRegex(
            self.src,
            r'gs_threshold,\s*threshold_warning\s*=\s*normalize_threshold_for_type',
            'the normalised value must be assigned back to gs_threshold, or the '
            'UPDATE still writes the unusable one')

    def test_the_warning_is_surfaced_to_the_caller(self):
        self.assertIn('threshold_warning', self.src)
        self.assertRegex(
            self.src, r"warnings\s*=\s*\[threshold_warning\]",
            'a reshaped threshold must reach result["warnings"], or the curator is '
            'never told the cutoff they asked for was not the one saved')


if __name__ == '__main__':
    unittest.main()
