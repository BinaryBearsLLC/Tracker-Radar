import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tracker_core as core


class ReleaseSafetyTests(unittest.TestCase):
    def test_unrecognized_status_is_never_exported(self):
        for status in ('UNTESTED', 'PENDING', 'unexpected'):
            results = {'url': core.TrackerResult('url', status, 'HTTP')}
            self.assertEqual(core.clean_trackers(['url'], results, include_unknown=True), [])

    def test_redirect_cannot_forward_hash_to_another_origin(self):
        reached = []
        class Target(BaseHTTPRequestHandler):
            def do_GET(self):
                reached.append(self.path)
                self.send_response(200)
                self.end_headers()
            def log_message(self, *args): pass
        target = ThreadingHTTPServer(('127.0.0.1', 0), Target)
        class Redirect(Target):
            def do_GET(self):
                self.send_response(302)
                self.send_header('Location', f'http://127.0.0.1:{target.server_port}/scrape?info_hash=private')
                self.end_headers()
        source = ThreadingHTTPServer(('127.0.0.1', 0), Redirect)
        for server in (target, source):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with self.assertRaises(core.InspectorError):
                core._http_get(f'http://127.0.0.1:{source.server_port}/scrape?info_hash=private', 2)
            self.assertEqual(reached, [])
        finally:
            for server in (target, source):
                server.shutdown()
                server.server_close()

    def test_same_origin_redirect_is_allowed(self):
        request = urllib.request.Request('https://example.org/scrape?info_hash=test')
        result = core.TrackerRedirectHandler().redirect_request(
            request, None, 302, 'Found', {}, 'https://example.org/new-scrape?info_hash=test')
        self.assertEqual(result.full_url, 'https://example.org/new-scrape?info_hash=test')

    def test_https_downgrade_is_blocked(self):
        with self.assertRaises(core.InspectorError):
            core.TrackerRedirectHandler().redirect_request(
                urllib.request.Request('https://example.org/scrape'), None, 302,
                'Found', {}, 'http://example.org/scrape')
