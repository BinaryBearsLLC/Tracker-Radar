import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracker_core import TrackerResult, clean_trackers


class CleanTests(unittest.TestCase):
    def setUp(self):
        self.results = {
            'active': TrackerResult('active', 'WORKING', 'UDP', seeders=3, peers=4),
            'no-seeds': TrackerResult('no-seeds', 'WORKING', 'UDP', seeders=0, peers=2),
            'no-peers': TrackerResult('no-peers', 'WORKING', 'UDP', seeders=3, peers=0),
            'empty': TrackerResult('empty', 'WORKING', 'UDP', seeders=0, peers=0),
            'unknown': TrackerResult('unknown', 'WORKING', 'UDP'),
            'review': TrackerResult('review', 'REVIEW', 'HTTPS'),
            'failed': TrackerResult('failed', 'FAILED', 'UDP'),
            'invalid': TrackerResult('invalid', 'INVALID', 'UDP'),
        }
        self.urls = list(self.results) + ['untested']

    def clean(self, **options):
        return clean_trackers(self.urls, self.results, **options)

    def test_default_keeps_working_without_swarm_assumptions(self):
        self.assertEqual(self.clean(), ['active', 'no-seeds', 'no-peers', 'empty', 'unknown'])

    def test_require_seeders(self):
        self.assertEqual(self.clean(zero_seeders=True, swarm_query=True), ['active', 'no-peers'])

    def test_require_peers(self):
        self.assertEqual(self.clean(zero_peers=True, swarm_query=True), ['active', 'no-seeds'])

    def test_require_both(self):
        self.assertEqual(self.clean(zero_peers=True, zero_seeders=True, swarm_query=True), ['active'])

    def test_unknown_is_opt_in_not_zero(self):
        self.assertEqual(self.clean(zero_peers=True, zero_seeders=True, swarm_query=True, include_unknown=True), ['active', 'unknown', 'review'])

    def test_never_exports_failed_invalid_or_untested(self):
        self.assertTrue(set(self.clean(include_unknown=True)).isdisjoint({'failed', 'invalid', 'untested'}))

    def test_zero_filters_ignored_without_swarm(self):
        self.assertEqual(self.clean(zero_seeders=True, zero_peers=True), self.clean())

    def test_does_not_modify_source_or_results(self):
        before = list(self.urls)
        self.clean(zero_seeders=True, swarm_query=True)
        self.assertEqual(self.urls, before)
        self.assertEqual(len(self.results), 8)

    def test_all_excluded_is_empty_not_fallback(self):
        self.assertEqual(clean_trackers(['empty'], self.results, zero_seeders=True, swarm_query=True), [])

    def test_duplicates_removed_preserving_order(self):
        self.assertEqual(clean_trackers(['active', 'active'], self.results), ['active'])
