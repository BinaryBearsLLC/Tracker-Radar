#!/usr/bin/env python3
"""Small, direct-to-tracker desktop diagnostics. BinaryBears."""
from __future__ import annotations

import csv
import multiprocessing as mp
import os
from pathlib import Path
import queue
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import tracker_core as core


def configure_tls():
    if getattr(sys, "frozen", False) and not os.environ.get("SSL_CERT_FILE"):
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()


def scan_job(channel, trackers, info_hash, timeout, workers, retry, fallback):
    configure_tls()
    try:
        core.test_trackers(trackers, info_hash=info_hash, timeout=timeout,
                           workers=workers, retry_failures=retry,
                           announce_fallback=fallback,
                           on_result=lambda result: channel.put(("result", result)))
    except Exception as exc:
        channel.put(("error", str(exc)))
    finally:
        channel.put(("done", None))


def load_job(channel, candidates):
    configure_tls()
    try:
        channel.put(("source", core.load_tracker_sources(candidates)))
    except Exception as exc:
        channel.put(("error", str(exc)))
    finally:
        channel.put(("done", None))


class App:
    def __init__(self, root):
        self.root = root
        self.trackers = []
        self.results = {}
        self.swarm = None
        self.process = None
        self.channel = None
        self.loading = False
        self.run_urls = []
        self.query_label = "Tracker availability"
        self.magnet_value = ""
        root.title("Tracker Radar · BinaryBears")
        root.geometry("1060x740")
        root.minsize(850, 620)
        root.configure(bg="#f3f5f7")
        root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(root)
        style.theme_use("clam")
        font = "SF Pro Text" if sys.platform == "darwin" else "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"
        style.configure(".", font=(font, 11), background="#f3f5f7", foreground="#1c2938")
        style.configure("TButton", background="#ffffff", bordercolor="#dce2e9", relief="flat", padding=(12, 7))
        style.map("TButton", background=[("active", "#e6edf4")])
        style.configure("Accent.TButton", background="#16665d", foreground="white", bordercolor="#16665d")
        style.map("Accent.TButton", background=[("active", "#104e47"), ("disabled", "#c6d6d3")], foreground=[("disabled", "#526b66")])
        style.configure("TEntry", fieldbackground="white", bordercolor="#dce2e9", padding=6)
        style.configure("TCombobox", fieldbackground="white", padding=5)
        style.configure("TCombobox", background="white", bordercolor="white", lightcolor="white", darkcolor="white", borderwidth=0, arrowsize=12)
        style.map("TCombobox", fieldbackground=[("readonly", "white")], foreground=[("readonly", "#1c2938")])
        style.configure("Treeview", rowheight=32, background="white", fieldbackground="white", borderwidth=0)
        style.configure("Treeview", bordercolor="white", lightcolor="white", darkcolor="white", relief="flat")
        for orient in ("Vertical", "Horizontal"):
            style.configure(f"{orient}.TScrollbar", background="#d4dde5", troughcolor="#f3f5f7", bordercolor="#f3f5f7", lightcolor="#d4dde5", darkcolor="#d4dde5", arrowsize=11, borderwidth=0, relief="flat")
        style.map("TCheckbutton", background=[("active", "#f3f5f7"), ("disabled", "#f3f5f7")], foreground=[("disabled", "#8c96a3")])
        style.configure("Treeview.Heading", background="#e9eef3", relief="flat", padding=8)
        style.map("Treeview", background=[("selected", "#d9eee9")], foreground=[("selected", "#123f37")])
        style.configure("Horizontal.TProgressbar", background="#16665d", troughcolor="#e2e8ed", borderwidth=0)
        style.configure("Title.TLabel", font=("TkDefaultFont", 22, "bold"))
        style.configure("Muted.TLabel", foreground="#647080")
        frame = ttk.Frame(root, padding=18)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(5, weight=1)
        header = ttk.Frame(frame)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        icon = Path(__file__).parent / "assets" / "icon.png"
        try:
            self.icon = tk.PhotoImage(file=str(icon))
            root.iconphoto(True, self.icon)
            self.small_icon = self.icon.subsample(max(1, self.icon.width() // 44))
            ttk.Label(header, image=self.small_icon).pack(side="left", padx=(0, 10))
        except tk.TclError:
            pass
        ttk.Label(header, text="Tracker Radar", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text=f"BinaryBears · {core.APP_VERSION} · MIT", style="Muted.TLabel").pack(side="right")
        source = ttk.Frame(frame)
        source.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        source.columnconfigure(0, weight=1)
        self.source = ttk.Combobox(source, state="readonly", values=list(core.NGOSANG_SOURCES))
        self.source.current(0)
        self.source.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.load_button = ttk.Button(source, text="Load list", command=self.load_source)
        self.load_button.grid(row=0, column=1, padx=3)
        ttk.Button(source, text="Import…", command=self.import_file).grid(row=0, column=2, padx=3)
        ttk.Button(source, text="Paste / URL…", command=self.add_dialog).grid(row=0, column=3, padx=3)
        ttk.Button(source, text="Help", command=self.help).grid(row=0, column=4, padx=(3, 0))
        swarm = ttk.Frame(frame)
        swarm.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        swarm.columnconfigure(1, weight=1)
        ttk.Label(swarm, text="Torrent").grid(row=0, column=0, padx=(0, 8))
        self.magnet = ttk.Entry(swarm)
        self.magnet.grid(row=0, column=1, sticky="ew")
        self.magnet.bind("<Return>", lambda _: self.use_magnet())
        ttk.Button(swarm, text="Use magnet", command=self.use_magnet).grid(row=0, column=2, padx=6)
        ttk.Button(swarm, text="Open .torrent…", command=self.open_torrent).grid(row=0, column=3)
        ttk.Button(swarm, text="Clear", command=self.clear_swarm).grid(row=0, column=4, padx=(6, 0))
        self.swarm_label = ttk.Label(frame, text="Optional: paste a magnet to query its seeders and peers.",
                                     style="Muted.TLabel", wraplength=950)
        self.swarm_label.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        bar = ttk.Frame(frame)
        bar.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        self.run_button = ttk.Button(bar, text="Test trackers", style="Accent.TButton", command=self.start)
        self.run_button.pack(side="left")
        self.stop_button = ttk.Button(bar, text="Stop", state="disabled", command=self.stop)
        self.stop_button.pack(side="left", padx=6)
        ttk.Button(bar, text="Settings…", command=self.settings).pack(side="left")
        ttk.Button(bar, text="Clear list", command=self.clear_list).pack(side="right")
        self.filter = tk.StringVar(value="All")
        filt = ttk.Combobox(bar, textvariable=self.filter, state="readonly", width=13,
                            values=["All", "Working", "Review", "Failed", "Invalid", "Untested"])
        filt.pack(side="right", padx=6)
        filt.bind("<<ComboboxSelected>>", lambda _: self.render())
        table = ttk.Frame(frame)
        table.grid(row=5, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        cols = ("tracker", "status", "ms", "seeds", "peers")
        self.tree = ttk.Treeview(table, columns=cols, show="headings", selectmode="extended")
        for name, title, width in zip(cols, ["Tracker", "Result", "ms", "Seeders", "Peers"], [470, 95, 65, 70, 70]):
            self.tree.heading(name, text=title, command=lambda c=name: self.sort(c))
            self.tree.column(name, width=width, minwidth=50, stretch=name == "tracker",
                             anchor="w" if name in ("tracker", "status") else "e")
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.tag_configure("WORKING", foreground="#16704e")
        self.tree.tag_configure("REVIEW", foreground="#94620e")
        self.tree.tag_configure("FAILED", foreground="#b13a40")
        self.tree.tag_configure("INVALID", foreground="#b13a40")
        self.tree.bind("<<TreeviewSelect>>", self.show_detail)
        self.tree.bind("<Double-1>", self.detail_dialog)
        self.detail = tk.StringVar(value="Load the ngosang list, import a file, or paste your trackers.")
        ttk.Label(frame, textvariable=self.detail, wraplength=930).grid(row=6, column=0, sticky="ew", pady=8)
        self.progress = ttk.Progressbar(frame, mode="determinate")
        self.progress.grid(row=7, column=0, sticky="ew")
        cleaning = ttk.Frame(frame)
        cleaning.grid(row=8, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(cleaning, text="Clean list", font=(font, 11, "bold")).pack(side="left", padx=(0, 14))
        self.zero_seeders = tk.BooleanVar(value=False)
        self.zero_peers = tk.BooleanVar(value=False)
        self.keep_unknown = tk.BooleanVar(value=False)
        self.seed_toggle = ttk.Checkbutton(cleaning, text="Exclude zero seeders", variable=self.zero_seeders, command=self.update_clean)
        self.seed_toggle.pack(side="left", padx=5)
        self.peer_toggle = ttk.Checkbutton(cleaning, text="Exclude zero peers", variable=self.zero_peers, command=self.update_clean)
        self.peer_toggle.pack(side="left", padx=5)
        ttk.Checkbutton(cleaning, text="Keep unknown / review", variable=self.keep_unknown, command=self.update_clean).pack(side="left", padx=5)
        self.clean_summary = tk.StringVar()
        ttk.Label(frame, textvariable=self.clean_summary, style="Muted.TLabel", wraplength=800).grid(row=9, column=0, sticky="ew", pady=(7, 0))
        footer = ttk.Frame(frame)
        footer.grid(row=10, column=0, sticky="ew", pady=(10, 0))
        self.summary = tk.StringVar(value="No trackers loaded")
        ttk.Label(footer, textvariable=self.summary).pack(side="left")
        ttk.Button(footer, text="Save TXT", style="Accent.TButton", command=self.save_clean).pack(side="right")
        ttk.Button(footer, text="Copy clean list", command=self.copy_working).pack(side="right", padx=6)
        self.update_clean()
        self.timeout = 5.0
        self.workers = 16
        self.retry = True
        self.fallback = True
        self.reverse = False
        modifier = "Command" if sys.platform == "darwin" else "Control"
        root.bind(f"<{modifier}-o>", lambda _: self.import_file())
        root.bind("<Escape>", lambda _: self.stop())
        root.bind("<Configure>", self.resize)
        root.after(80, self.poll)

    def resize(self, event):
        if event.widget is self.root:
            width = max(300, event.width - 45)
            self.swarm_label.configure(wraplength=width)
            # Keep long URLs/details from setting the window's requested width.
            for row in (6, 9):
                for child in self.swarm_label.master.grid_slaves(row=row):
                    child.configure(wraplength=width)

    def idle(self):
        if self.process or self.loading:
            messagebox.showinfo("Task in progress", "Stop the current test or wait for the list to load.", parent=self.root)
            return False
        return True

    def add(self, text):
        try:
            self.trackers = core.dedupe_trackers(self.trackers + core.parse_tracker_text(text))
            self.render()
        except core.InspectorError as exc:
            self.error(exc)

    def fetch(self, candidates):
        if not self.idle():
            return
        self.loading = True
        self.load_button.configure(state="disabled")
        self.detail.set("Loading tracker list…")
        self.channel = mp.get_context("spawn").Queue()
        self.process = mp.get_context("spawn").Process(
            target=load_job, args=(self.channel, candidates), daemon=True)
        self.process.start()
        self.run_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

    def load_source(self):
        self.fetch(core.ngosang_mirrors(core.NGOSANG_SOURCES[self.source.get()]))

    def import_file(self):
        if not self.idle():
            return
        path = filedialog.askopenfilename(filetypes=[("Tracker lists", "*.txt"), ("All files", "*")])
        if path:
            try:
                if Path(path).stat().st_size > core.MAX_LIST_BODY:
                    raise ValueError("Tracker lists must be smaller than 5 MB.")
                self.add(Path(path).read_text(encoding="utf-8-sig"))
            except Exception as exc:
                self.error(exc)

    def add_dialog(self):
        if not self.idle():
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Add trackers")
        dialog.geometry("620x330")
        ttk.Label(dialog, text="Paste tracker addresses, or a link to a .txt list.", padding=12).pack(anchor="w")
        entry = tk.Text(dialog, height=9, wrap="word", undo=True)
        entry.pack(fill="both", expand=True, padx=12)
        def accept():
            if not self.idle():
                return
            value = entry.get("1.0", "end").strip()
            if not value:
                return
            dialog.destroy()
            self.add(value)
        def load():
            value = entry.get("1.0", "end").strip()
            dialog.destroy()
            self.fetch((value,))
        buttons = ttk.Frame(dialog, padding=12)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Add trackers", command=accept).pack(side="right")
        ttk.Button(buttons, text="Load as list URL", command=load).pack(side="right", padx=8)
        entry.focus_set()

    def set_swarm(self, swarm):
        self.swarm = swarm
        self.results.clear()
        self.add("\n".join(swarm.trackers))
        private = "Private torrent: only its embedded trackers will be queried. " if swarm.private else ""
        self.swarm_label.configure(text=f"{swarm.name} · {swarm.source_kind}\n{private}{swarm.display_hash}")
        self.detail.set("Torrent ready. Click Test trackers to query its swarm.")

    def use_magnet(self):
        if self.idle():
            try:
                self.set_swarm(core.parse_magnet(self.magnet.get().strip()))
                self.magnet_value = self.magnet.get().strip()
            except Exception as exc:
                self.error(exc)

    def open_torrent(self):
        if not self.idle():
            return
        path = filedialog.askopenfilename(filetypes=[("Torrent files", "*.torrent")])
        if path:
            try:
                self.set_swarm(core.parse_torrent_file(path))
                self.magnet.delete(0, "end")
                self.magnet_value = ""
            except Exception as exc:
                self.error(exc)

    def clear_swarm(self):
        if self.idle():
            self.swarm = None
            self.magnet_value = ""
            self.results.clear()
            self.magnet.delete(0, "end")
            self.swarm_label.configure(text="Optional: paste a magnet to query its seeders and peers.")
            self.render()

    def clear_list(self):
        if self.idle() and (not self.trackers or messagebox.askyesno("Clear list", "Remove this list and its results?")):
            self.trackers.clear()
            self.results.clear()
            self.render()

    def start(self):
        if not self.idle():
            return
        if self.magnet.get().strip() and self.magnet.get().strip() != self.magnet_value:
            self.use_magnet()
            if self.magnet.get().strip() != self.magnet_value:
                return
        urls = core.trackers_for_query(self.trackers, self.swarm)
        if not urls:
            self.error("Load or paste a tracker list first. Private torrents need embedded tracker URLs.")
            return
        self.results.clear()
        self.run_urls = urls
        self.query_label = self.swarm.display_hash if self.swarm else "Tracker availability"
        self.render()
        self.progress.configure(maximum=len(urls), value=0)
        self.channel = mp.get_context("spawn").Queue()
        self.process = mp.get_context("spawn").Process(target=scan_job, args=(
            self.channel, urls, self.swarm.info_hash if self.swarm else None,
            self.timeout, self.workers, self.retry, self.fallback), daemon=True)
        self.process.start()
        self.run_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.detail.set("Testing directly from your connection. No files are downloaded.")

    def finish(self, stopped=False):
        process, channel = self.process, self.channel
        self.process = self.channel = None
        if process:
            if process.is_alive():
                process.terminate()
            process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join(timeout=1)
            process.close()
        if channel:
            channel.close()
        self.loading = False
        self.load_button.configure(state="normal")
        self.run_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.detail.set("Stopped. Completed results are kept." if stopped else
                        "Done. Working = valid protocol response. Review ≠ dead. Double-click a row for details.")

    def stop(self):
        if self.process:
            self.finish(True)

    def poll(self):
        changed = False
        try:
            while self.channel:
                kind, payload = self.channel.get_nowait()
                if kind == "result":
                    self.results[payload.url] = payload
                    changed = True
                elif kind == "source":
                    self.add("\n".join(payload[0]))
                elif kind == "error":
                    self.error(payload)
                elif kind == "done":
                    self.finish()
        except queue.Empty:
            pass
        if changed:
            self.render()
            self.progress.configure(value=len(self.results))
        if self.process and self.process.exitcode is not None:
            # A clean worker sends 'done' before exit; allow its queue feeder to flush.
            self.finish(True)
            self.detail.set("Worker exited. Completed results are kept; you can run the test again.")
        self.root.after(100, self.poll)

    def render(self):
        selected = self.tree.selection()
        position = self.tree.yview()[0]
        self.tree.delete(*self.tree.get_children())
        count = {name: 0 for name in ("WORKING", "REVIEW", "FAILED", "INVALID")}
        for index, url in enumerate(self.trackers):
            result = self.results.get(url)
            status = result.status if result else "UNTESTED"
            if result:
                count[status] += 1
            if self.filter.get().upper() not in ("ALL", status):
                continue
            values = [url, status.title()]
            values.extend("—" if v is None else v for v in
                          ((result.latency_ms, result.seeders, result.peers) if result else (None, None, None)))
            self.tree.insert("", "end", iid=str(index), values=values, tags=(status,))
        for item in selected:
            if self.tree.exists(item):
                self.tree.selection_add(item)
        self.tree.yview_moveto(position)
        self.summary.set(f"{len(self.trackers)} total · {count['WORKING']} working · {count['REVIEW']} review · {count['FAILED'] + count['INVALID']} failed/invalid")
        self.update_clean()

    def sort(self, column):
        def key(item):
            value = self.tree.set(item, column)
            return int(value) if value.isdigit() else (-1 if column in ("ms", "seeds", "peers") else value.lower())
        for index, item in enumerate(sorted(self.tree.get_children(), key=key, reverse=self.reverse)):
            self.tree.move(item, "", index)
        self.reverse = not self.reverse

    def detail_text(self):
        items = self.tree.selection()
        if not items:
            return "Select a tracker to see its response."
        url = self.trackers[int(items[0])]
        result = self.results.get(url)
        if not result:
            return f"{url}\nNot tested."
        return (f"{url}\n{result.status.title()} · {result.method} · {result.checked_at}\n"
                f"{result.detail}\nQuery: {self.query_label}\n"
                f"Completed downloads: {result.completed if result.completed is not None else 'not reported'}")

    def show_detail(self, _=None):
        items = self.tree.selection()
        result = self.results.get(self.trackers[int(items[0])]) if items else None
        self.detail.set(result.detail if result else "Not tested. Double-click for the complete tracker address.")

    def detail_dialog(self, _=None):
        messagebox.showinfo("Tracker details", self.detail_text(), parent=self.root)

    def working(self):
        return core.clean_trackers(self.trackers, self.results,
            zero_seeders=self.zero_seeders.get(), zero_peers=self.zero_peers.get(),
            include_unknown=self.keep_unknown.get(), swarm_query=self.swarm is not None)

    def update_clean(self):
        if not hasattr(self, "clean_summary"):
            return
        state = "normal" if self.swarm else "disabled"
        self.seed_toggle.configure(state=state)
        self.peer_toggle.configure(state=state)
        kept = len(self.working())
        if not self.swarm:
            note = "Add a torrent or magnet to filter seeders and peers."
        else:
            checked = [r for r in self.results.values()]
            seeds = sum(r.seeders is not None and r.seeders > 0 for r in checked)
            peers = sum(r.peers is not None and r.peers > 0 for r in checked)
            no_seeds = sum(r.seeders == 0 for r in checked)
            no_peers = sum(r.peers == 0 for r in checked)
            unknown = sum(r.seeders is None or r.peers is None for r in checked)
            note = f"Trackers: {seeds} with seeds / {no_seeds} zero · {peers} with peers / {no_peers} zero · {unknown} unknown"
        self.clean_summary.set(f"{kept} kept · {len(self.trackers) - kept} excluded from export. {note}")

    def save_clean(self):
        urls = self.working()
        if not urls:
            self.error("Nothing matches the clean filters. Run a test or change the filters.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="trackers-clean.txt", filetypes=[("Tracker list", "*.txt")])
        if path:
            try:
                Path(path).write_text("\n\n".join(urls) + "\n", encoding="utf-8")
                self.detail.set("Clean list saved. The original list is unchanged.")
            except OSError as exc:
                self.error(exc)

    def copy_working(self):
        urls = self.working()
        if not urls:
            self.error("Nothing matches the clean filters. Run a test or change the filters.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append("\n\n".join(urls) + "\n")
        self.detail.set("Clean list copied. Paste it into qBittorrent.")

    def export_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Export")
        dialog.resizable(False, False)
        ttk.Label(dialog, text="Save a tracker list or the full test report.", padding=16).pack()
        def save(mode):
            urls = self.working() if mode == "working" else ([url for url in self.trackers if url in self.results and self.results[url].status in ("FAILED", "INVALID")] if mode == "excluded" else self.trackers)
            if not urls:
                self.error("There are no entries to save.")
                return
            extension = ".csv" if mode == "report" else ".txt"
            path = filedialog.asksaveasfilename(parent=dialog, defaultextension=extension,
                                               initialfile=f"trackers-{mode}{extension}")
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8", newline="") as stream:
                    if mode == "report":
                        writer = csv.writer(stream)
                        writer.writerow(["Tracker", "Status", "Latency ms", "Seeders", "Peers", "Completed", "Method", "Detail", "Checked UTC", "Query"])
                        for url in urls:
                            r = self.results.get(url)
                            row = [url, r.status if r else "UNTESTED"]
                            row += [r.latency_ms, r.seeders, r.peers, r.completed, r.method, r.detail, r.checked_at] if r else [""] * 7
                            row += [self.query_label if r else ""]
                            writer.writerow([("'" + v) if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) else v for v in row])
                    else:
                        stream.write("\n\n".join(urls) + "\n")
                dialog.destroy()
                self.detail.set(f"Saved {Path(path).name}")
            except OSError as exc:
                self.error(exc)
        for mode, label in [("working", "Working only (.txt)"), ("excluded", "Failed / invalid (.txt)"), ("all", "All trackers (.txt)"), ("report", "Full report (.csv)")]:
            ttk.Button(dialog, text=label, command=lambda m=mode: save(m)).pack(fill="x", padx=16, pady=(0, 10))

    def settings(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings")
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=18)
        frame.pack()
        values = []
        for row, (label, value, low, high) in enumerate([("Timeout per request (seconds)", self.timeout, 2, 30), ("Concurrent trackers", self.workers, 1, 32)]):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=6)
            var = tk.StringVar(value=str(value))
            ttk.Spinbox(frame, from_=low, to=high, textvariable=var, width=7).grid(row=row, column=1, padx=12)
            values.append(var)
        retry = tk.BooleanVar(value=self.retry)
        fallback = tk.BooleanVar(value=self.fallback)
        ttk.Checkbutton(frame, text="Retry failed trackers once", variable=retry).grid(row=2, columnspan=2, sticky="w")
        ttk.Checkbutton(frame, text="Try a stopped announce when scrape is unavailable", variable=fallback).grid(row=3, columnspan=2, sticky="w")
        def save():
            try:
                timeout, workers = float(values[0].get()), int(values[1].get())
                if not 2 <= timeout <= 30 or not 1 <= workers <= 32:
                    raise ValueError("Use a timeout of 2–30 seconds and 1–32 concurrent trackers.")
                self.timeout, self.workers = timeout, workers
                self.retry, self.fallback = retry.get(), fallback.get()
                dialog.destroy()
            except ValueError as exc:
                self.error(exc)
        ttk.Button(frame, text="Done", command=save).grid(row=4, column=1, pady=(12, 0))

    def help(self):
        messagebox.showinfo("About Tracker Radar", f"Tracker Radar {core.APP_VERSION} · BinaryBears · MIT License\n\n"
            "1. Load the ngosang list, or import your own.\n"
            "2. Optionally add a magnet or .torrent.\n"
            "3. Test, select your clean filters, then copy or save.\n\n"
            "Zero-seeder and zero-peer filters require a torrent. Unknown counts are excluded unless Keep unknown / review is selected. Failed, invalid and untested rows never enter the clean export. Cleaning does not alter the original list.\n\n"
            "Working: valid BitTorrent protocol reply.\nReview: answered, but needs attention (for example authentication or an unknown hash).\n"
            "Failed: this test failed from your connection; not proof of a permanent outage.\n\n"
            "UDP, HTTP and HTTPS are tested directly. WebTorrent WebSocket trackers are not qBittorrent endpoints. "
            "No proxy, telemetry, DHT or content downloads. Tracker requests reveal your IP and the queried hash to the tracker. "
            "Stopped announces may be logged. Magnets cannot identify private torrents; use the original .torrent for private swarms.\n\n"
            "Counts are tracker-reported, not totals across the network. Peers means incomplete peers. "
            "Private torrent queries use only their embedded trackers. Lists are not saved automatically. "
            "Exported files may contain private passkeys; share carefully.\n\n"
            "List source: github.com/ngosang/trackerslist", parent=self.root)

    def error(self, error):
        messagebox.showerror("Tracker Radar", str(error), parent=self.root)

    def close(self):
        self.stop()
        self.root.destroy()


def main():
    mp.freeze_support()
    configure_tls()
    if "--version" in sys.argv:
        print(core.APP_VERSION)
        return
    root = tk.Tk()
    app = App(root)
    if "--smoke-test" in sys.argv:
        # Exercise the bundled interpreter, Tk, spawned worker and result queue.
        app.add("udp://127.0.0.1:0/announce")
        root.after(100, app.start)
        def check():
            if app.results:
                app.close()
            else:
                root.after(100, check)
        root.after(200, check)
        root.after(15000, app.close)
    root.mainloop()
    if "--smoke-test" in sys.argv:
        if len(app.results) != 1 or next(iter(app.results.values())).status != "INVALID":
            raise RuntimeError("Bundled GUI/worker smoke test did not complete")


if __name__ == "__main__":
    main()
