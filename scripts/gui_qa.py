"""Exercise real Tk controls with local protocol fixtures and temporary files.
Native dialogs are stubbed; this does not claim manual dialog/desktop QA.
"""
import multiprocessing as mp
from pathlib import Path
import sys
import tempfile
import threading
import time
import tkinter as tk
from unittest.mock import patch
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from tracker_radar import App
import tracker_core as core
from test_core import FakeHTTPTracker, bencode


def main():
    root = tk.Tk()
    app = App(root)
    errors = []
    app.error = lambda error: errors.append(str(error))
    server = ThreadingHTTPServer(('127.0.0.1', 0), FakeHTTPTracker)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/announce'
    def wait_done():
        deadline = time.monotonic() + 15
        while app.process and time.monotonic() < deadline:
            root.update()
            time.sleep(.02)
        assert app.process is None, 'Worker did not finish'
        assert not errors, errors
    try:
        root.geometry('850x620')
        root.update()
        assert root.winfo_width() == 850
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'trackers.txt'
            source.write_text(url + '\n', encoding='utf-8')
            with patch('tracker_radar.filedialog.askopenfilename', return_value=str(source)):
                app.import_file()
            app.magnet.insert(0, 'magnet:?xt=urn:btih:' + '12' * 20)
            app.use_magnet()
            app.start()
            wait_done()
            assert app.results[url].seeders == 7
            assert app.results[url].peers == 3
            # Exercise both zero filters with deterministic reported results.
            app.add('https://zero.example/announce\nhttps://unknown.example/announce')
            zero, unknown = app.trackers[1:]
            app.results[zero] = core.TrackerResult(zero, 'WORKING', 'HTTPS', seeders=0, peers=0)
            app.results[unknown] = core.TrackerResult(unknown, 'REVIEW', 'HTTPS')
            original = list(app.trackers)
            for toggle in (app.zero_seeders, app.zero_peers):
                toggle.set(True)
                app.update_clean()
                assert app.working() == [url]
                toggle.set(False)
            app.zero_seeders.set(True)
            app.zero_peers.set(True)
            app.copy_working()
            root.update()
            assert root.clipboard_get() == url + '\n'
            output = Path(temp) / 'clean.txt'
            with patch('tracker_radar.filedialog.asksaveasfilename', return_value=str(output)):
                app.save_clean()
            assert output.read_text() == url + '\n'
            assert app.trackers == original
            torrent = Path(temp) / 'private.torrent'
            torrent.write_bytes(bencode({b'announce': url.encode(), b'info': {
                b'name': b'Local fixture', b'pieces': b'x' * 20, b'piece length': 16384,
                b'length': 1, b'private': 1}}))
            with patch('tracker_radar.filedialog.askopenfilename', return_value=str(torrent)):
                app.open_torrent()
            app.start()
            wait_done()
            assert app.run_urls == [url]
            app.clear_swarm()
            app.trackers = ['udp://127.0.0.1:9/announce']
            app.timeout = 30
            app.start()
            root.update()
            process = app.process
            app.stop()
            assert app.process is None
            app.trackers = [url]
            app.start()
            wait_done()
            assert app.results[url].status == 'WORKING'
            app.fetch([f'http://127.0.0.1:{server.server_port}/missing'])
            app.stop()
            assert not app.loading and app.process is None
        print('GUI QA passed: min size, TXT import, magnet/torrent, private routing, results, both filters, clipboard, saved TXT, stop/retest and load cancellation. Dialogs stubbed.')
    finally:
        app.close()
        server.shutdown()
        server.server_close()

if __name__ == '__main__':
    mp.freeze_support()
    main()
