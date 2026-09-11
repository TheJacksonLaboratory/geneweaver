"""
Regression test: a threshold the database cannot cast must never reach the write
(G3-823).

Found by test T3 of the 1.6.0b SQA verification pass. A curator changing a gene set's
score type from a two-sided type (Correlation/Effect, threshold "low,high") to a
one-sided one (P-Value/Q-Value, a single number) without also editing the threshold
field got "An unknown error ocurred." and lost the change.

The UPDATE itself is legal -- production.geneset.gs_threshold is character varying, so
"0.0,10.0" stores fine. What fails is the AFTER UPDATE trigger:
geneset_threshold_update_trigger -> process_thresholds, which casts the threshold --
`cast(gs_threshold as numeric)` for the one-sided types,
`string_to_array(gs_threshold, ',')::numeric[]` for the two-sided ones. Either cast
raising aborts the trigger, and the whole statement rolls back.

normalize_threshold_for_type is the server-side half of the fix; editgenesets.html
reshapes the field client-side, which is what makes the requirement visible. Its
contract is narrow and worth stating: what it returns must always be something the
matching cast accepts.

Verified against geneweaver-sqa when this was written:
    cast('1_0' as numeric)                    -> raises (but Python float() accepts it)
    cast('0x1' as numeric)                    -> raises (but JS Number() accepts it)
    string_to_array('0x1,0x2',',')::numeric[] -> raises
    string_to_array('',',')::numeric[]        -> {} , casts cleanly
    string_to_array('0.05',',')::numeric[]    -> {0.05}, casts cleanly

Run from legacy/:  python -m unittest tests.db.test_score_type_threshold_shape
"""
import inspect
import io
import json
import os
import re
import shutil
import subprocess
import unittest

from tests.db import _shims

_shims.install()
from src.geneweaverdb import (  # noqa: E402
    DEFAULT_ONE_SIDED_THRESHOLD,
    DEFAULT_THRESHOLDS,
    ONE_SIDED_THRESHOLD_TYPES,
    PG_NUMERIC_RE,
    PG_NUMERIC_SPECIALS,
    TWO_SIDED_THRESHOLD_TYPES,
    _stores_as_pg_numeric,
    _stores_as_pg_numeric_array,
    normalize_threshold_for_type,
    update_geneset,
)

P_VALUE, Q_VALUE, BINARY, CORRELATION, EFFECT = 1, 2, 3, 4, 5

LEGACY = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

## Spellings Python's float() or JavaScript's Number() accept but PostgreSQL's numeric
## does not, plus literals past numeric's declared digit limits. Each one silently
## passed an earlier version of this check straight through to the trigger -- the
## float() cases were Copilot's catch, the out-of-bounds ones a later review's.
## Boundaries measured on PostgreSQL 15.18.
NOT_PG_NUMERIC = ['1_0', '1_000.5', '0x1', '0b1', '1e', '.', '+', 'junk', 'P < 0.05',
                  '0.05;DROP', '[]', '1e131072', '1e-16384']

## Accepted by numeric and therefore NOT corrected, even though none is a sensible
## cutoff. Changing them would move membership on existing gene sets, which CLAUDE.md
## requires be measured and approved on its own rather than folded into a crash fix --
## and `1 < 'NaN'::numeric` is TRUE in PostgreSQL, so a NaN cutoff puts every gene *in*
## threshold rather than emptying the set. 0 live gene sets on SQA carry one.
PG_ACCEPTED_SPECIALS = ['nan', 'NaN', 'inf', '-inf', 'Infinity', '-Infinity']

## Everything the numeric cast does accept, including the awkward spellings migration
## 119's regex exists to keep: a bare leading dot, a trailing dot, an explicit plus.
IS_PG_NUMERIC = ['0.05', '0.01', '0', '1', '-1', '+3.03', '.5', '15.', '2.0E-8',
                 '6.76e-05', '1e-300', '  0.05  ',
                 ## the exact boundaries numeric still stores
                 '1e131071', '1e-16383']


class GrammarTests(unittest.TestCase):
    def test_the_grammar_accepts_what_numeric_accepts(self):
        for value in IS_PG_NUMERIC:
            self.assertTrue(PG_NUMERIC_RE.match(value), repr(value))

    def test_the_grammar_rejects_bad_syntax(self):
        for value in ['1_0', '1_000.5', '0x1', '0b1', '1e', '.', '+', 'junk', '', '   ']:
            self.assertFalse(PG_NUMERIC_RE.match(value), repr(value))

    def test_float_would_not_have_been_a_substitute(self):
        # The point of using a grammar rather than float(): these parse in Python and
        # are rejected by the database, so a float()-based check hands the trigger a
        # value it cannot store. Guards against anyone "simplifying" this back.
        for value in ('1_0', '1_000.5'):
            float(value)  # no exception -- that is the trap
            self.assertFalse(PG_NUMERIC_RE.match(value), repr(value))

    def test_the_grammar_alone_is_not_enough(self):
        # Syntax is necessary but not sufficient: these match the literal grammar and
        # still raise "value overflows numeric format", so the check has to consider
        # numeric's declared digit limits too.
        for value in ('1e131072', '1e-16384'):
            self.assertTrue(PG_NUMERIC_RE.match(value), repr(value))
            self.assertFalse(_stores_as_pg_numeric(value), repr(value))

    def test_the_storable_check_matches_measured_postgres_behaviour(self):
        # Each expectation here was run against geneweaver-sqa (PostgreSQL 15.18).
        for value in IS_PG_NUMERIC + PG_ACCEPTED_SPECIALS:
            self.assertTrue(_stores_as_pg_numeric(value), repr(value))
        for value in NOT_PG_NUMERIC + ['', '   ']:
            self.assertFalse(_stores_as_pg_numeric(value), repr(value))

    def test_the_special_spellings_are_listed_lowercase_for_folding(self):
        self.assertEqual(PG_NUMERIC_SPECIALS,
                         frozenset(v.lower() for v in PG_NUMERIC_SPECIALS))

    def test_the_grammar_matches_the_one_migration_119_uses(self):
        # Both exist to describe the same thing (what numeric will cast). If one is
        # ever loosened the other has to move with it.
        path = os.path.join(LEGACY, 'migration',
                            '119-fix-correlation-effect-abs-threshold.sql')
        with io.open(path, encoding='utf-8') as fh:
            sql = fh.read()
        for fragment in (r'[0-9]+\.?[0-9]*|\.[0-9]+', r'[eE][+-]?[0-9]+'):
            self.assertIn(fragment, sql,
                          'migration 119 no longer carries this fragment of the '
                          'numeric grammar; PG_NUMERIC_RE and the migration have '
                          'drifted apart')
            self.assertIn(fragment, PG_NUMERIC_RE.pattern)


class OneSidedTests(unittest.TestCase):
    def test_the_reported_case_is_corrected(self):
        # The exact reproduction from G3-823: GS408080 was Effect "0.0,10.0" and was
        # switched to P-Value with the threshold field untouched.
        threshold, warning = normalize_threshold_for_type(P_VALUE, '0.0,10.0')

        self.assertEqual(threshold, '0.05')
        self.assertIsNotNone(
            warning, 'a substituted threshold must be reported, not applied silently')

    def test_a_range_is_corrected_for_both_one_sided_types(self):
        for ttype in ONE_SIDED_THRESHOLD_TYPES:
            for value in ('0.0,10.0', '-1,1', '-1000,1000', '0.05,0.01'):
                threshold, warning = normalize_threshold_for_type(ttype, value)
                self.assertEqual(threshold, DEFAULT_ONE_SIDED_THRESHOLD,
                                 'type %s / %r' % (ttype, value))
                self.assertIsNotNone(warning, 'type %s / %r' % (ttype, value))

    def test_python_only_spellings_are_corrected(self):
        # Copilot's review catch: float('1_0') is 10.0, but cast('1_0' as numeric)
        # raises, so the original check returned it unchanged and a direct-POST save
        # still rolled back.
        for value in NOT_PG_NUMERIC:
            for ttype in ONE_SIDED_THRESHOLD_TYPES:
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
        for value in IS_PG_NUMERIC:
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

    def test_a_missing_threshold_gets_the_default(self):
        for value in ('', None, '   '):
            threshold, warning = normalize_threshold_for_type(P_VALUE, value)
            self.assertEqual(threshold, DEFAULT_ONE_SIDED_THRESHOLD, repr(value))
            self.assertIsNotNone(warning, repr(value))


class TwoSidedTests(unittest.TestCase):
    """The two-sided cast raises too -- on content, not on the number of components --
    so Correlation/Effect need the same guard. Copilot's review catch: the form's old
    Number() check accepted '0x1,0x2' as a valid pair, and the server did not look at
    two-sided thresholds at all, so the save still aborted."""

    def test_an_uncastable_pair_is_corrected(self):
        for value in ('0x1,0x2', '1_0,2', 'junk', 'a,b', '0.05,junk', ',', '1,'):
            for ttype in TWO_SIDED_THRESHOLD_TYPES:
                threshold, warning = normalize_threshold_for_type(ttype, value)
                self.assertEqual(threshold, DEFAULT_THRESHOLDS[ttype],
                                 'type %s / %r' % (ttype, value))
                self.assertIsNotNone(warning, 'type %s / %r' % (ttype, value))

    def test_effect_does_not_borrow_correlations_range(self):
        # Copilot's review catch: the form used -1,1 for both. Ordinary effect sizes
        # run well outside [-1,1], so an Effect set given Correlation's range would
        # silently exclude values a fresh Effect upload would have kept.
        self.assertEqual(DEFAULT_THRESHOLDS[EFFECT], '-1000,1000')
        self.assertEqual(DEFAULT_THRESHOLDS[CORRELATION], '-1,1')

        effect, _ = normalize_threshold_for_type(EFFECT, 'junk')
        correlation, _ = normalize_threshold_for_type(CORRELATION, 'junk')
        self.assertEqual(effect, '-1000,1000')
        self.assertEqual(correlation, '-1,1')
        self.assertNotEqual(effect, correlation)

    def test_valid_ranges_are_left_alone(self):
        for value in ('-1,1', '-1000,1000', '0.0,10.0', '.5,1.1', '1,15.',
                      '-1.42,+3.03', '6.76e-05,0.011', ' -1 , 1 '):
            for ttype in TWO_SIDED_THRESHOLD_TYPES:
                threshold, warning = normalize_threshold_for_type(ttype, value)
                self.assertEqual(threshold, value, 'type %s / %r' % (ttype, value))
                self.assertIsNone(warning, 'type %s / %r' % (ttype, value))

    def test_a_single_number_under_a_two_sided_type_is_left_alone(self):
        # string_to_array('0.05', ',')::numeric[] is a legal one-element array, so this
        # does not raise: the proc's BETWEEN is merely NULL and nothing is in
        # threshold. That is the pre-existing P-Value -> Correlation result 1.6.0a's C2
        # test signed off, and this fix deliberately does not change it.
        for ttype in TWO_SIDED_THRESHOLD_TYPES:
            threshold, warning = normalize_threshold_for_type(ttype, '0.05')
            self.assertEqual(threshold, '0.05')
            self.assertIsNone(warning)

    def test_an_empty_two_sided_threshold_is_left_alone(self):
        # string_to_array('', ',') is the empty array -- zero components, nothing to
        # cast -- so this is not a crash either and is not ours to change.
        for ttype in TWO_SIDED_THRESHOLD_TYPES:
            threshold, warning = normalize_threshold_for_type(ttype, '')
            self.assertEqual(threshold, '')
            self.assertIsNone(warning)


class UntouchedTypeTests(unittest.TestCase):
    def test_binary_is_never_touched(self):
        # GWC-44: a binary set is a membership list and is not thresholded at all, so
        # its threshold is never cast and any value in it is harmless.
        for value in ('1', '0.0,10.0', '', 'anything', '0x1'):
            threshold, warning = normalize_threshold_for_type(BINARY, value)
            self.assertEqual(threshold, value)
            self.assertIsNone(warning)

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


class ContractTests(unittest.TestCase):
    def test_results_are_always_castable(self):
        # The contract: whatever goes in, what comes out is something the cast for that
        # type accepts. This is the assertion that keeps the trigger from ever aborting
        # a save again.
        junk = (NOT_PG_NUMERIC + IS_PG_NUMERIC + PG_ACCEPTED_SPECIALS +
                ['0.0,10.0', '-1,1', '', None, '   ', ',', '1,', ',1', '0.05,',
                 '0x1,0x2', '1_0,2', 'a,b', '1,2,3', '1e131072,1', 'nan,1'])
        for ttype in ONE_SIDED_THRESHOLD_TYPES + TWO_SIDED_THRESHOLD_TYPES:
            for value in junk:
                threshold, _ = normalize_threshold_for_type(ttype, value)
                text = '' if threshold is None else str(threshold)
                check = (_stores_as_pg_numeric if ttype in ONE_SIDED_THRESHOLD_TYPES
                         else _stores_as_pg_numeric_array)
                self.assertTrue(check(text),
                                'type %s / %r produced unstorable %r'
                                % (ttype, value, threshold))

    def test_the_defaults_match_the_upload_paths(self):
        # These are duplicated in geneweaverdb because uploadfiles imports it and not
        # the other way round. Read uploadfiles' source rather than importing it (it
        # needs `requests`, which the pure-unit environment does not have) and pin the
        # two together so they cannot drift -- an Effect default of -1,1 here would
        # silently disagree with what a fresh Effect upload gets.
        path = os.path.join(LEGACY, 'src', 'uploadfiles.py')
        with io.open(path, encoding='utf-8') as fh:
            src = fh.read()
        start = src.index('def get_default_threshold')
        body = src[start:src.index('\ndef ', start + 1)]

        pairs = re.findall(r"t == '(\d)':[^\n]*\n\s*return '([^']*)'", body)
        self.assertTrue(pairs, 'could not read the mapping out of '
                               'uploadfiles.get_default_threshold; this drift guard '
                               'needs rewriting against its new shape')

        found = {int(t): value for t, value in pairs}
        self.assertEqual(found, DEFAULT_THRESHOLDS,
                         'geneweaverdb.DEFAULT_THRESHOLDS and '
                         'uploadfiles.get_default_threshold disagree')

    def test_the_warning_names_the_score_type_the_shape_and_the_value(self):
        _, warning = normalize_threshold_for_type(Q_VALUE, '0.0,10.0')
        self.assertIn('Q-Value', warning)
        self.assertIn('single cutoff', warning)
        self.assertIn('0.0,10.0', warning,
                      'the curator needs to see what was discarded')
        self.assertIn(DEFAULT_ONE_SIDED_THRESHOLD, warning,
                      'and what it was replaced with')

        _, warning = normalize_threshold_for_type(EFFECT, 'junk')
        self.assertIn('Effect', warning)
        self.assertIn('low,high', warning)
        self.assertIn('-1000,1000', warning)


class BoundsAndSpecialsTests(unittest.TestCase):
    """Raised in review of PR #14: matching numeric's grammar is not the same as being
    storable, and the spellings numeric *does* accept are not ours to rewrite."""

    def test_out_of_bounds_literals_are_corrected(self):
        for value in ('1e131072', '1e-16384'):
            for ttype in ONE_SIDED_THRESHOLD_TYPES:
                threshold, warning = normalize_threshold_for_type(ttype, value)
                self.assertEqual(threshold, DEFAULT_ONE_SIDED_THRESHOLD,
                                 'type %s / %r' % (ttype, value))
                self.assertIsNotNone(warning, 'type %s / %r' % (ttype, value))

    def test_the_boundary_values_are_left_alone(self):
        # One digit further out raises; these do not. Asserting the boundary rather
        # than just the failure keeps the bound from being tightened by guesswork.
        for value in ('1e131071', '1e-16383'):
            for ttype in ONE_SIDED_THRESHOLD_TYPES:
                threshold, warning = normalize_threshold_for_type(ttype, value)
                self.assertEqual(threshold, value, 'type %s / %r' % (ttype, value))
                self.assertIsNone(warning, 'type %s / %r' % (ttype, value))

    def test_out_of_bounds_components_are_corrected_for_two_sided_types(self):
        for ttype in TWO_SIDED_THRESHOLD_TYPES:
            threshold, warning = normalize_threshold_for_type(ttype, '1e131072,1')
            self.assertEqual(threshold, DEFAULT_THRESHOLDS[ttype])
            self.assertIsNotNone(warning)

    def test_numerics_own_special_spellings_are_left_alone(self):
        # NaN and infinity cast fine (measured on 15.18), so correcting them would be a
        # membership change rather than a crash fix -- and `1 < 'NaN'::numeric` is TRUE,
        # so a NaN cutoff puts every gene IN threshold. CLAUDE.md wants that measured
        # and approved separately, so this PR leaves them exactly as they are.
        for value in PG_ACCEPTED_SPECIALS:
            for ttype in ONE_SIDED_THRESHOLD_TYPES + TWO_SIDED_THRESHOLD_TYPES:
                threshold, warning = normalize_threshold_for_type(ttype, value)
                self.assertEqual(threshold, value, 'type %s / %r' % (ttype, value))
                self.assertIsNone(warning, 'type %s / %r' % (ttype, value))


NODE = shutil.which('node') or shutil.which('nodejs')

JS_FRAGMENTS = (
    r'var PG_NUMERIC = /.*?/;',
    r'var DEFAULT_THRESHOLD = \{[\s\S]*?\};',
    r'function thresholdFitsType[\s\S]*?\n        \}',
    r'function nextThresholdValue[\s\S]*?\n        \}',
)

JS_DRIVER = """
%(code)s
var drafts = {};
var prev = %(start_type)s, value = %(start_value)s;
drafts[prev] = value;
%(hops)s.forEach(function (t) {
    value = nextThresholdValue(t, prev, value, drafts);
    prev = t;
});
console.log(JSON.stringify(value));
"""


@unittest.skipUnless(NODE, 'node is not on PATH; the client-side check is skipped')
class EditFormRoundTripTests(unittest.TestCase):
    """The client half, exercised for real rather than asserted on source.

    Raised in review of PR #14: reshaping on every score-type change was lossy on a
    round trip. Correlation '-0.2,0.2' -> P-Value became '0.05', and selecting
    Correlation again saw a single number, decided it was not a pair and overwrote it
    with the default '-1,1'. The curator's range was gone -- and because '-1,1' is
    itself valid, the server had nothing to warn about, so the loss was silent and
    would have recomputed membership on save.

    nextThresholdValue is deliberately jQuery-free so it can be lifted out of the
    template and run directly.
    """

    @classmethod
    def setUpClass(cls):
        path = os.path.join(LEGACY, 'src', 'templates', 'editgenesets.html')
        with io.open(path, encoding='utf-8') as fh:
            cls.src = fh.read()

    def _run(self, hops, start_type, start_value):
        """Replay a sequence of score-type selections through the template's own
        function and return the value the threshold field would hold."""
        code = []
        for pattern in JS_FRAGMENTS:
            m = re.search(pattern, self.src)
            self.assertIsNotNone(
                m, 'could not lift %r out of editgenesets.html; the client fix has '
                   'been reshaped and this test needs rewriting' % pattern)
            code.append(m.group(0))

        driver = JS_DRIVER % {
            'code': '\n'.join(code),
            'start_type': json.dumps(start_type),
            'start_value': json.dumps(start_value),
            'hops': json.dumps(hops),
        }
        out = subprocess.check_output([NODE, '-e', driver], stderr=subprocess.STDOUT)
        return json.loads(out.decode().strip())

    def test_a_round_trip_restores_the_curators_range(self):
        # The reviewer's exact scenario.
        self.assertEqual(
            self._run(['1', '4'], '4', '-0.2,0.2'), '-0.2,0.2',
            'a Correlation -> P-Value -> Correlation round trip must give the custom '
            'range back, not the -1,1 default')

    def test_a_round_trip_restores_a_custom_cutoff(self):
        self.assertEqual(self._run(['4', '1'], '1', '2.0E-8'), '2.0E-8')

    def test_an_incompatible_threshold_still_gets_a_default(self):
        # Nothing banked for the new type -- the whole point of the original fix.
        self.assertEqual(self._run(['1'], '4', '-0.2,0.2'), '0.05')
        self.assertEqual(self._run(['5'], '1', '0.05'), '-1000,1000')
        self.assertEqual(self._run(['4'], '1', '0.05'), '-1,1')

    def test_a_compatible_threshold_is_never_rewritten(self):
        # Correlation -> Effect: both two-sided, so the range carries over untouched.
        self.assertEqual(self._run(['5'], '4', '-0.2,0.2'), '-0.2,0.2')
        self.assertEqual(self._run(['2'], '1', '0.01'), '0.01')

    def test_binary_does_not_discard_the_threshold(self):
        # A binary set is not thresholded (GWC-44), so passing through Binary must not
        # destroy the value the curator had for the type they came from.
        self.assertEqual(self._run(['3', '4'], '4', '-0.2,0.2'), '-0.2,0.2')

    def test_the_form_and_the_server_share_one_grammar(self):
        m = re.search(r'var PG_NUMERIC = /(.*?)/;', self.src)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), PG_NUMERIC_RE.pattern,
                         'the form and the server must test the same numeric grammar, '
                         'or one will accept a threshold the other rejects')

    def test_the_form_and_the_server_share_one_set_of_defaults(self):
        m = re.search(r'var DEFAULT_THRESHOLD = \{([\s\S]*?)\};', self.src)
        self.assertIsNotNone(m)
        found = {int(t): v for t, v in re.findall(r"'(\d)':\s*'([^']*)'", m.group(1))}
        self.assertEqual(found, DEFAULT_THRESHOLDS)


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
                            'update_geneset no longer normalises the threshold; a '
                            'threshold the database cannot cast aborts the save in the '
                            'AFTER UPDATE trigger (G3-823)')
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
