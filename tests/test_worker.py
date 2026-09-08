import multiprocessing as mp
import sys
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracker_radar import scan_job
from test_core import FakeHTTPTracker, UDPTracker


class WorkerTests(unittest.TestCase):
    def test_spawned_worker_queries_http_and_udp(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeHTTPTracker)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        udp = UDPTracker()
        udp.start()
        context = mp.get_context("spawn")
        channel = context.Queue()
        urls = [f"http://127.0.0.1:{httpd.server_port}/announce", f"udp://127.0.0.1:{udp.port}/announce"]
        process = context.Process(target=scan_job, args=(channel, urls, b"x" * 20, 2, 2, False, False))
        try:
            process.start()
            results = []
            while True:
                kind, payload = channel.get(timeout=15)
                if kind == "done":
                    break
                self.assertEqual(kind, "result", payload)
                results.append(payload)
            process.join(timeout=5)
            self.assertEqual(process.exitcode, 0)
            self.assertEqual({r.protocol for r in results}, {"HTTP", "UDP"})
            self.assertTrue(all(r.status == "WORKING" for r in results))
            self.assertEqual(sorted(r.seeders for r in results), [7, 11])
        finally:
            if process.is_alive():
                process.terminate()
                process.join()
            process.close()
            channel.close()
            httpd.shutdown()
            httpd.server_close()
            udp.close()

    def test_worker_can_be_stopped_during_network_wait(self):
        context = mp.get_context("spawn")
        channel = context.Queue()
        process = context.Process(target=scan_job, args=(channel, ["udp://127.0.0.1:9/announce"], None, 30, 1, True, True))
        process.start()
        time.sleep(0.3)
        started = time.monotonic()
        process.terminate()
        process.join(timeout=2)
        self.assertFalse(process.is_alive())
        self.assertLess(time.monotonic() - started, 2)
        process.close()
        channel.close()


if __name__ == "__main__":
    unittest.main()
