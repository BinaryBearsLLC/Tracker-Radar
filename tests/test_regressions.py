import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tracker_core as core
from test_core import bencode


class AccuracyTests(unittest.TestCase):
    def test_unrelated_hash_never_supplies_counts(self):
        with self.assertRaises(core.UnknownSwarm):
            core._counts_from_scrape({b"files": {b"x" * 20: {b"complete": 90, b"incomplete": 40}}}, b"y" * 20)

    def test_empty_scrape_is_unknown_not_zero(self):
        with self.assertRaises(core.UnknownSwarm):
            core._counts_from_scrape({b"files": {}}, b"x" * 20)

    def test_missing_counts_not_invented(self):
        with self.assertRaises(core.InspectorError):
            core._counts_from_scrape({b"files": {b"x" * 20: {}}}, b"x" * 20)

    def test_unknown_swarm_is_review(self):
        with patch.object(core, "_http_get", return_value=(200, bencode({b"files": {}}), "https://example.org/scrape", 10)):
            result = core.probe_http_tracker("https://example.org/announce", b"x" * 20, 2, False)
        self.assertEqual(result.status, "REVIEW")
        self.assertIsNone(result.seeders)

    def test_empty_scrape_still_proves_protocol_health(self):
        with patch.object(core, "_http_get", return_value=(200, bencode({b"files": {}}), "https://example.org/scrape", 10)):
            result = core.probe_http_tracker("https://example.org/announce", None, 2, False)
        self.assertEqual(result.status, "WORKING")
        self.assertIsNone(result.seeders)

    def test_real_zero_is_preserved(self):
        self.assertEqual(core._counts_from_scrape({b"files": {b"x" * 20: {b"complete": 0, b"incomplete": 0}}}, b"x" * 20), (0, 0, 0))

    def test_private_flag_and_raw_hash(self):
        info = {b"name": b"fixture", b"pieces": b"x" * 20, b"piece length": 16384, b"length": 1, b"private": 1}
        context = core.parse_torrent_bytes(bencode({b"info": info, b"announce": b"https://example.org/announce?passkey=fixture"}))
        self.assertTrue(context.private)
        self.assertEqual(context.info_hash, hashlib.sha1(bencode(info)).digest())
        self.assertEqual(len(context.trackers), 1)

    def test_invalid_metainfo_rejected(self):
        with self.assertRaises(core.InspectorError):
            core.parse_torrent_bytes(bencode({b"info": {b"name": b"not a torrent"}}))

    def test_private_query_excludes_added_public_trackers(self):
        swarm = core.SwarmContext(b"x" * 20, "hash", "name", ("https://private.example/announce",), "v1", private=True)
        self.assertEqual(core.trackers_for_query(["udp://public.example:80/announce"], swarm), list(swarm.trackers))

    def test_private_without_embedded_trackers_sends_nothing(self):
        swarm = core.SwarmContext(b"x" * 20, "hash", "name", (), "v1", private=True)
        self.assertEqual(core.trackers_for_query(["udp://public.example:80/announce"], swarm), [])

    def test_root_path_allowed(self):
        self.assertTrue(core.validate_tracker_url("https://example.org")[0])

    def test_wss_not_exported_as_qbittorrent_tracker(self):
        self.assertEqual(core.probe_tracker("wss://example.org/", None, 2, False).status, "INVALID")

    def test_html_is_not_a_tracker(self):
        with patch.object(core, "_http_get", return_value=(200, b"<html>Hello</html>", "https://example.org/scrape", 10)):
            result = core.probe_http_tracker("https://example.org/announce", None, 2, False)
        self.assertFalse(result.exportable)

    def test_review_is_not_exportable(self):
        self.assertFalse(core.TrackerResult("https://example.org/announce", "REVIEW", "HTTPS").exportable)

    def test_tracker_like_html_is_only_review(self):
        with patch.object(core, "_http_get", return_value=(200, b"<html>Missing info_hash on announce</html>", "https://example.org/announce", 10)):
            result = core._http_announce_probe("https://example.org/announce", None, 2)
        self.assertEqual(result.status, "REVIEW")

    def test_swarm_failure_not_a_working_swarm(self):
        self.assertEqual(core._failure_status("temporarily unavailable", swarm_query=True)[0], "REVIEW")

    def test_websocket_imported_then_explicitly_invalid(self):
        self.assertEqual(core.parse_tracker_text("wss://example.org/"), ["wss://example.org/"])

    def test_health_probe_does_not_display_unscoped_counts(self):
        with patch.object(core, "_http_get", return_value=(200, bencode({b"interval": 100, b"complete": 99}), "https://example.org/announce", 10)):
            result = core._http_announce_probe("https://example.org/announce", None, 2)
        self.assertEqual(result.status, "WORKING")
        self.assertIsNone(result.seeders)

    def test_malformed_announce_interval_not_working(self):
        with patch.object(core, "_http_get", return_value=(200, bencode({b"interval": b"broken"}), "https://example.org/announce", 10)):
            result = core._http_announce_probe("https://example.org/announce", None, 2)
        self.assertFalse(result.exportable)


if __name__ == "__main__":
    unittest.main()
