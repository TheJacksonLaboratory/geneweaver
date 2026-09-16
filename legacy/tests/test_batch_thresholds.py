"""
Regression tests for BatchReader score-type parsing and threshold membership.

Covers:
* GWC-44 / G3-776 -- binary gene sets are NOT thresholded: __check_thresholds
  returns in-threshold for every binary value (including 0), so binary sets stay
  usable in the analysis tools (which filter on gsv_in_threshold).
* GWC-42 / G3-772 -- __parse_score_type maps score types correctly and parses
  the correlation/effect *upper* bound (the fix that turns
  "0.0 < correlation < 0.5" into "0.0,0.5" rather than the old "0.0,.0").
* NCBI requests carry finite timeouts, and optional SRA metadata degrades to an
  empty value when NCBI is unavailable or rate-limits the application.

Pure unit tests: geneweaverdb / pubmedsvc are mocked so no DB is needed.
Run from legacy/:  python -m unittest tests.test_batch_thresholds
"""
import importlib.util
import os
import sys
import types
import unittest
from unittest.mock import MagicMock

# geneweaverdb opens a DB connection pool at import; mock it (and pubmedsvc)
# before importing batch so these stay pure/no-DB unit tests.
sys.modules['geneweaverdb'] = MagicMock()
sys.modules['pubmedsvc'] = MagicMock()

from src.batch import BatchReader


class _RequestException(Exception):
    pass


_fake_requests = types.ModuleType('requests')
# requests 2.32.4 re-exports RequestException at the package root as well as under
# .exceptions (verified against the deployed image: both names are the same object).
# Mirror both so the fake cannot bless a spelling the real library does not have.
_fake_requests.exceptions = types.SimpleNamespace(
    RequestException=_RequestException)
_fake_requests.RequestException = _RequestException
_fake_requests.get = MagicMock()
_old_requests = sys.modules.get('requests')
sys.modules['requests'] = _fake_requests
_pubmedsvc_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                               'src', 'pubmedsvc.py')
_pubmedsvc_spec = importlib.util.spec_from_file_location(
    '_pubmedsvc_timeout_tests', _pubmedsvc_path)
pubmedsvc_under_test = importlib.util.module_from_spec(_pubmedsvc_spec)
_pubmedsvc_spec.loader.exec_module(pubmedsvc_under_test)
if _old_requests is None:
    del sys.modules['requests']
else:
    sys.modules['requests'] = _old_requests


class _Response:
    def __init__(self, body, error=None):
        self.content = body.encode('utf-8')
        self.text = body
        self._error = error

    def raise_for_status(self):
        if self._error:
            raise self._error


class PubMedTimeoutTests(unittest.TestCase):
    """NCBI calls are bounded and optional SRA metadata fails open."""

    def setUp(self):
        _fake_requests.get.reset_mock()
        _fake_requests.get.side_effect = None

    def test_pubmed_metadata_request_has_timeout(self):
        _fake_requests.get.return_value = _Response(
            '<PubmedArticle><ArticleTitle>Example</ArticleTitle></PubmedArticle>')

        result = pubmedsvc_under_test.get_pubmed_info('123')

        self.assertEqual('Example', result['pub_title'])
        self.assertEqual('123', result['pub_pubmed'])
        self.assertEqual(pubmedsvc_under_test.NCBI_TIMEOUT,
                         _fake_requests.get.call_args.kwargs['timeout'])

    def test_sra_lookup_has_timeout_on_both_requests(self):
        _fake_requests.get.side_effect = [
            _Response('<LinkSet><LinkSetDb><Link><Id>456</Id></Link>'
                      '</LinkSetDb></LinkSet>'),
            _Response('<EXPERIMENT_PACKAGE><STUDY><IDENTIFIERS>'
                      '<PRIMARY_ID>SRP000001</PRIMARY_ID>'
                      '</IDENTIFIERS></STUDY></EXPERIMENT_PACKAGE>'),
        ]

        result = pubmedsvc_under_test.get_SRP('123')

        self.assertEqual('SRP000001', result)
        self.assertEqual(2, _fake_requests.get.call_count)
        for call in _fake_requests.get.call_args_list:
            self.assertEqual(pubmedsvc_under_test.NCBI_TIMEOUT,
                             call.kwargs['timeout'])

    def test_sra_rate_limit_degrades_to_missing_metadata(self):
        _fake_requests.get.return_value = _Response(
            '', _RequestException('HTTP 429'))

        with self.assertLogs(pubmedsvc_under_test.logger, level='WARNING'):
            result = pubmedsvc_under_test.get_SRP('123')

        self.assertEqual('', result)
        self.assertEqual(1, _fake_requests.get.call_count)

    def test_sra_missing_link_skips_second_request(self):
        _fake_requests.get.return_value = _Response('<LinkSet/>')

        self.assertEqual('', pubmedsvc_under_test.get_SRP('123'))
        self.assertEqual(1, _fake_requests.get.call_count)


class BinaryThresholdTests(unittest.TestCase):
    """GWC-44: a binary gene set is a membership list; every value is in-threshold."""

    def setUp(self):
        self.reader = BatchReader('')

    def _in_threshold(self, ttype, threshold, value):
        return self.reader._BatchReader__check_thresholds(ttype, threshold, value)

    def test_binary_value_one_is_in_threshold(self):
        self.assertTrue(self._in_threshold(3, 1.0, '1'))

    def test_binary_value_zero_is_in_threshold(self):
        # The bug: value 0 was flagged out-of-threshold (value >= 1 in Python,
        # value > 1 in the DB proc), making binary sets unusable in tools.
        # It must now be in-threshold.
        self.assertTrue(self._in_threshold(3, 1.0, '0'))

    def test_binary_in_threshold_regardless_of_stored_threshold(self):
        # Real binary thresholds in the data are inconsistent ('1', '0.5', '0');
        # none of them should ever exclude a listed gene.
        for thresh in (0.0, 0.5, 1.0):
            self.assertTrue(self._in_threshold(3, thresh, '0'))
            self.assertTrue(self._in_threshold(3, thresh, '1'))


class PQThresholdTests(unittest.TestCase):
    """p-value / q-value: in-threshold when value <= threshold (no regression)."""

    def setUp(self):
        self.reader = BatchReader('')

    def _in(self, ttype, threshold, value):
        return self.reader._BatchReader__check_thresholds(ttype, threshold, value)

    def test_pvalue_below_threshold_in(self):
        self.assertTrue(self._in(1, 0.05, '0.01'))

    def test_pvalue_on_the_boundary_is_out(self):
        # EXCLUSIVE (G3-819). This asserted True ("boundary inclusive") until
        # 2026-09-04, when the deployed behaviour was measured: every type-1/2 row
        # sitting exactly on its cutoff was out-of-threshold in both readable
        # environments, because production.process_thresholds uses `<` and is the
        # effective writer. The decision was to match Prod rather than change
        # published membership, so this path was the outlier, not the proc.
        self.assertFalse(self._in(1, 0.05, '0.05'))
        self.assertFalse(self._in(2, 0.05, '0.05'))

    def test_pvalue_above_threshold_out(self):
        self.assertFalse(self._in(1, 0.05, '0.06'))

    def test_qvalue_behaves_like_pvalue(self):
        self.assertTrue(self._in(2, 0.05, '0.01'))
        self.assertFalse(self._in(2, 0.05, '0.10'))


class CorrelationEffectThresholdTests(unittest.TestCase):
    """correlation / effect: in-threshold when min <= value <= max (no regression)."""

    def setUp(self):
        self.reader = BatchReader('')

    def _in(self, ttype, threshold, value):
        return self.reader._BatchReader__check_thresholds(ttype, threshold, value)

    def test_correlation_within_range_in(self):
        self.assertTrue(self._in(4, [-1.0, 1.0], '0.5'))
        self.assertTrue(self._in(4, [-1.0, 1.0], '-1'))   # lower boundary
        self.assertTrue(self._in(4, [-1.0, 1.0], '1'))    # upper boundary

    def test_correlation_outside_range_out(self):
        self.assertFalse(self._in(4, [-1.0, 1.0], '2'))
        self.assertFalse(self._in(4, [-1.0, 1.0], '-2'))

    def test_effect_range(self):
        self.assertTrue(self._in(5, [-1000.0, 1000.0], '500'))
        self.assertFalse(self._in(5, [-1000.0, 1000.0], '2000'))


class ParseScoreTypeTests(unittest.TestCase):
    """GWC-42: __parse_score_type returns (type, threshold) with correct bounds."""

    def setUp(self):
        self.reader = BatchReader('')

    def _parse(self, s):
        return self.reader._BatchReader__parse_score_type(s)

    def test_binary(self):
        self.assertEqual(self._parse('Binary'), (3, '1'))
        self.assertEqual(self._parse('binary'), (3, '1'))

    def test_correlation_uses_upper_bound(self):
        # GWC-42 fix: upper bound comes from regex group(3), so this parses to
        # "0.0,0.5" -- not the old buggy "0.0,.0".
        stype, thresh = self._parse('0.0 < correlation < 0.5')
        self.assertEqual(stype, 4)
        self.assertEqual(thresh, '0.0,0.5')

    def test_correlation_negative_range(self):
        stype, thresh = self._parse('-0.75 < correlation < 0.75')
        self.assertEqual(stype, 4)
        self.assertEqual(thresh, '-0.75,0.75')

    def test_effect_uses_upper_bound(self):
        stype, thresh = self._parse('6.0 < effect < 22.50')
        self.assertEqual(stype, 5)
        self.assertEqual(thresh, '6.0,22.50')

    def test_correlation_invalid_defaults_and_warns(self):
        stype, thresh = self._parse('correlation')  # no range given
        self.assertEqual(stype, 4)
        self.assertEqual(thresh, '-1,1')
        self.assertTrue(self.reader.warns)

    def test_pvalue_type_detected(self):
        stype, _ = self._parse('p-value')
        self.assertEqual(stype, 1)

    def test_qvalue_type_detected(self):
        stype, _ = self._parse('q-value')
        self.assertEqual(stype, 2)

    # G3-811: the documented "P-Value < 0.05" form must round-trip the requested
    # threshold instead of being silently replaced with 0.05. The bug was that the
    # whole line was passed to a bare-number validator, so it never matched.
    def test_pvalue_threshold_roundtrips(self):
        stype, thresh = self._parse('P-Value < 0.01')
        self.assertEqual((stype, thresh), (1, '0.01'))
        self.assertFalse(self.reader.warns)

    def test_qvalue_threshold_roundtrips(self):
        stype, thresh = self._parse('Q-Value < 0.001')
        self.assertEqual((stype, thresh), (2, '0.001'))
        self.assertFalse(self.reader.warns)

    def test_pvalue_bare_keyword_defaults_without_warning(self):
        # No threshold requested -> default 0.05, and no spurious "invalid" warning.
        stype, thresh = self._parse('p-value')
        self.assertEqual((stype, thresh), (1, '0.05'))
        self.assertFalse(self.reader.warns)

    # G3-811 follow-up (PR #12 review): only an EXACT bare keyword may default
    # silently. A wrong or missing operator is a malformed header, and treating it like
    # the bare keyword replaced the user's cutoff with 0.05 with no signal at all.
    def test_pvalue_wrong_operator_warns_and_defaults(self):
        stype, thresh = self._parse('P-Value > 0.01')
        self.assertEqual((stype, thresh), (1, '0.05'))
        self.assertTrue(self.reader.warns)

    def test_pvalue_missing_operator_warns_and_defaults(self):
        stype, thresh = self._parse('P-Value 0.01')
        self.assertEqual((stype, thresh), (1, '0.05'))
        self.assertTrue(self.reader.warns)

    def test_qvalue_wrong_operator_warns_and_defaults(self):
        stype, thresh = self._parse('Q-Value > 0.01')
        self.assertEqual((stype, thresh), (2, '0.05'))
        self.assertTrue(self.reader.warns)

    def test_pvalue_bare_keyword_with_whitespace_still_silent(self):
        # Trailing whitespace is still a bare keyword, not a malformed header.
        stype, thresh = self._parse('  P-Value  ')
        self.assertEqual((stype, thresh), (1, '0.05'))
        self.assertFalse(self.reader.warns)

    def test_pvalue_out_of_range_warns_and_defaults(self):
        # A value outside [0, 1] is a real error: warn and fall back to 0.05.
        stype, thresh = self._parse('p-value < 1.5')
        self.assertEqual((stype, thresh), (1, '0.05'))
        self.assertTrue(self.reader.warns)

    def test_unknown_score_type_records_error(self):
        self._parse('nonsense')
        self.assertTrue(self.reader.errors)


if __name__ == '__main__':
    unittest.main()
