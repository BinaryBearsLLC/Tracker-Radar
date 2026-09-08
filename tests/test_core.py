from __future__ import annotations

import hashlib
import importlib.util
import socket
import struct
import sys
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock


APP_PATH = Path(__file__).parents[1] / "tracker_core.py"
SPEC = importlib.util.spec_from_file_location("tracker_inspector", APP_PATH)
assert SPEC and SPEC.loader
tti = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = tti
SPEC.loader.exec_module(tti)


def bencode(value):
    if isinstance(value, int):
        return b"i" + str(value).encode() + b"e"
    if isinstance(value, bytes):
        return str(len(value)).encode() + b":" + value
    if isinstance(value, list):
        return b"l" + b"".join(bencode(item) for item in value) + b"e"
    if isinstance(value, dict):
        return b"d" + b"".join(bencode(key) + bencode(value[key]) for key in sorted(value)) + b"e"
    raise TypeError(value)


class FakeHTTPTracker(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/scrape":
            query = urllib.parse.parse_qs(parsed.query, encoding="latin-1")
            # Recover raw percent-encoded bytes without a text round-trip.
            raw_hash = urllib.parse.unquote_to_bytes(parsed.query.split("info_hash=", 1)[1].split("&", 1)[0])
            body = bencode(
                {
                    b"files": {
                        raw_hash: {b"complete": 7, b"downloaded": 19, b"incomplete": 3}
                    }
                }
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/announce":
            body = bencode({b"failure reason": b"missing info_hash"})
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def log_message(self, *_args):
        pass


class UDPTracker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.1)
        self.port = self.sock.getsockname()[1]
        self.running = True
        self.connection_id = 0x1234567812345678

    def run(self):
        while self.running:
            try:
                data, address = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            if len(data) >= 16:
                action = struct.unpack("!I", data[8:12])[0]
                transaction = struct.unpack("!I", data[12:16])[0]
                if action == 0:
                    self.sock.sendto(struct.pack("!IIQ", 0, transaction, self.connection_id), address)
                elif action == 2:
                    self.sock.sendto(struct.pack("!IIIII", 2, transaction, 11, 29, 5), address)

    def close(self):
        self.running = False
        self.join(timeout=1)
        self.sock.close()


class InspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeHTTPTracker)
        cls.http_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.http_thread.start()
        cls.udp = UDPTracker()
        cls.udp.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.udp.close()

    def test_tracker_text_parse_and_dedupe(self):
        value = """# list
        udp://tracker.example:80/announce
        https://tracker.example/announce
        UDP://tracker.example:80/announce
        junk https://second.example/x, more
        """
        self.assertEqual(
            tti.parse_tracker_text(value),
            [
                "udp://tracker.example:80/announce",
                "https://tracker.example/announce",
                "https://second.example/x",
            ],
        )

    def test_magnet_v1_and_embedded_tracker(self):
        raw_hash = bytes(range(20))
        magnet = (
            "magnet:?xt=urn:btih:"
            + raw_hash.hex()
            + "&dn=Test&tr=udp%3A%2F%2Ftracker.example%3A80%2Fannounce"
        )
        context = tti.parse_magnet(magnet)
        self.assertEqual(context.info_hash, raw_hash)
        self.assertEqual(context.name, "Test")
        self.assertEqual(context.trackers, ("udp://tracker.example:80/announce",))

    def test_magnet_base32(self):
        raw_hash = b"a" * 20
        encoded = __import__("base64").b32encode(raw_hash).decode()
        context = tti.parse_magnet(f"magnet:?xt=urn:btih:{encoded}")
        self.assertEqual(context.info_hash, raw_hash)

    def test_torrent_v1_raw_info_hash_and_trackers(self):
        info = {b"length": 4, b"name": b"file", b"piece length": 4, b"pieces": b"x" * 20}
        raw_info = bencode(info)
        data = bencode(
            {
                b"announce": b"udp://primary.example:80/announce",
                b"announce-list": [[b"https://backup.example/announce"]],
                b"info": info,
            }
        )
        context = tti.parse_torrent_bytes(data)
        self.assertEqual(context.info_hash, hashlib.sha1(raw_info).digest())
        self.assertEqual(len(context.trackers), 2)

    def test_v2_torrent_uses_truncated_sha256(self):
        info = {
            b"file tree": {b"file": {b"": {b"length": 0}}},
            b"meta version": 2,
            b"name": b"v2",
            b"piece length": 16384,
        }
        raw_info = bencode(info)
        context = tti.parse_torrent_bytes(bencode({b"info": info}))
        self.assertEqual(context.info_hash, hashlib.sha256(raw_info).digest()[:20])
        self.assertEqual(len(context.display_hash), 64)

    def test_url_validation(self):
        self.assertTrue(tti.validate_tracker_url("https://example.com/announce")[0])
        self.assertTrue(tti.validate_tracker_url("udp://example.com:6969/announce")[0])
        self.assertFalse(tti.validate_tracker_url("udp://example.com/announce")[0])
        self.assertFalse(tti.validate_tracker_url("ftp://example.com/announce")[0])
        self.assertFalse(tti.validate_tracker_url("http://example.com:0/announce")[0])

    def test_ngosang_presets_are_supported_raw_lists(self):
        self.assertEqual(len(tti.NGOSANG_SOURCES), 5)
        for filename in tti.NGOSANG_SOURCES.values():
            self.assertTrue(filename.endswith(".txt"))
            mirrors = tti.ngosang_mirrors(filename)
            self.assertEqual(len(mirrors), 3)
            self.assertTrue(
                mirrors[0].startswith(
                    "https://raw.githubusercontent.com/ngosang/trackerslist/"
                )
            )
            self.assertTrue(all(url.endswith(filename) for url in mirrors))

    def test_failed_tracker_is_retried_once_and_can_recover(self):
        failed = tti.TrackerResult(
            "https://tracker.example/announce",
            "FAILED",
            "HTTPS",
            detail="temporary timeout",
            method="probe",
        )
        recovered = tti.TrackerResult(
            "https://tracker.example/announce",
            "WORKING",
            "HTTPS",
            latency_ms=42,
            detail="Valid scrape response",
            method="scrape",
        )
        with mock.patch.object(tti, "probe_tracker", side_effect=[failed, recovered]) as probe:
            results = tti.test_trackers(
                ["https://tracker.example/announce"],
                workers=1,
                retry_failures=True,
            )
        self.assertEqual(probe.call_count, 2)
        self.assertEqual(results[0].status, "WORKING")
        self.assertIn("automatic retry", results[0].detail)
        self.assertIn("retry", results[0].method)

    def test_tracker_source_uses_next_mirror_after_failure(self):
        mirrors = (
            "https://first.example/trackers.txt",
            "https://second.example/trackers.txt",
        )
        with mock.patch.object(
            tti,
            "load_tracker_url",
            side_effect=[tti.InspectorError("offline"), "udp://tracker.example:80/announce\n"],
        ) as loader:
            trackers, loaded_url = tti.load_tracker_sources(mirrors)
        self.assertEqual(loader.call_count, 2)
        self.assertEqual(loaded_url, mirrors[1])
        self.assertEqual(trackers, ["udp://tracker.example:80/announce"])

    def test_http_tracker_scrape(self):
        url = f"http://127.0.0.1:{self.httpd.server_port}/announce"
        result = tti.probe_tracker(url, b"z" * 20, 2.0, True)
        self.assertEqual(result.status, "WORKING")
        self.assertEqual((result.seeders, result.peers, result.completed), (7, 3, 19))
        self.assertEqual(result.method, "scrape")

    def test_http_tracker_health(self):
        url = f"http://127.0.0.1:{self.httpd.server_port}/announce"
        result = tti.probe_tracker(url, None, 2.0, True)
        self.assertEqual(result.status, "WORKING")
        self.assertEqual(result.method, "scrape")

    def test_udp_tracker_connect_and_scrape(self):
        url = f"udp://127.0.0.1:{self.udp.port}/announce"
        health = tti.probe_tracker(url, None, 2.0, True)
        self.assertEqual(health.status, "WORKING")
        result = tti.probe_tracker(url, b"q" * 20, 2.0, True)
        self.assertEqual(result.status, "WORKING")
        self.assertEqual((result.seeders, result.peers, result.completed), (11, 5, 29))


if __name__ == "__main__":
    unittest.main()
