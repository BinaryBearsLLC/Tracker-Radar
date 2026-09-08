# Tracker Radar 1.0.0 — verification

## Local checks — 8 September 2026

- Original local 3.1.0 archives: all three SHA-256 hashes passed before changes; archives remain unchanged in ignored `prebuilt/`.
- Source: 47 unittest checks passed, including local HTTP/UDP protocol fixtures, hash accuracy, private routing, worker cancellation, clean filters and new cross-origin redirect protections.
- Real Tk control harness: minimum size, TXT import, magnet/torrent parsing, private routing, response display, both zero filters, clipboard contents, saved TXT contents, original-list preservation, stop/retest and list-load cancellation passed. Native file dialogs are stubbed in this harness. Separately, the real macOS Open dialog imported a TXT fixture using the keyboard shortcut and native path selection; the loaded-row count increased. Default and minimum-size app screenshots were visually inspected.
- macOS: new Universal build with local Python 3.13.14/Tk; ARM64 and x86_64 (Rosetta) packaged smoke passed. All 54 Mach-O files include both architectures. Strict/deep Developer ID signature verification passed. Notarization is not established.
- Linux: new x64 package built with Python 3.13.15 in Debian 12 under Docker x64 emulation on Apple Silicon. Tests and packaged Xvfb smoke passed; ELF x86-64 architecture confirmed. Native hosted evidence is recorded separately below.
- Live network: valid UDP reply from tracker.opentrackr.org and valid HTTPS scrape response from torrent.ubuntu.com. Ubuntu's HTTP endpoint attempted a cross-origin redirect and was blocked. Availability observations are time/connection specific, not permanent uptime guarantees.
- Website: static assets, internal anchors, English language, three versioned download links and checksum link validated. Desktop light/dark and mobile screenshots inspected in Chromium; no horizontal overflow at 320, 390 or 1440 px. Auto follows emulated OS color changes, selected themes persist across reload, download navigation and FAQ disclosure work. The public page returned HTTP 200 with no broken images or browser console warnings/errors.

## Hosted checks

All three platform jobs and release publication passed for tag `v1.0.0`:
[release run 34223217689](https://github.com/BinaryBearsLLC/Tracker-Radar/actions/runs/34223217689).
The pre-tag main build also passed: [34223013689](https://github.com/BinaryBearsLLC/Tracker-Radar/actions/runs/34223013689).

Each target passed all 47 tests, source GUI/worker smoke, the Tk control harness, packaged smoke and architecture verification. Windows ran natively on Windows Server 2022 AMD64; Linux ran Debian 12 in a container on an x64 runner with Xvfb; macOS ran on ARM64 with an additional x86_64 packaged smoke via Rosetta. The Mac architecture check covered 54 Mach-O files.

GitHub Pages deployed successfully: [34223013683](https://github.com/BinaryBearsLLC/Tracker-Radar/actions/runs/34223013683).
Public site: https://binarybearsllc.github.io/Tracker-Radar/

The automated macOS artifact is ad-hoc signed. The public 1.0.0 Mac download is replaced with the locally Developer ID signed Universal build of the same tagged application source, built using Python 3.13.14. Its extracted archive passed ARM/Intel smoke and strict/deep signature verification. It is **not notarized**. Windows and Linux downloads come from the tagged CI run. Final public archive hashes are recorded below.

## Limits

A smoke test verifies startup, Tk, the bundled runtime and spawned worker/result queue. It is not a full manual desktop test. Physical Windows x64 and Intel Mac visual QA, full screen-reader testing, Windows Authenticode signing, macOS notarization and testing every supported OS version are not established. Linux requires glibc 2.36+ and a graphical X11/XWayland session.

The website's app screenshot uses labelled demonstration data. No fixture counts are presented as live swarm data. Tracker counters are never unique totals across trackers.

```text
8cf8a8901509dde57701b27a9917c61c341068c3897d2e5bdadb150ce785e482  Tracker-Radar-1.0.0-Linux-x64.tar.gz
02ac77b4ad5336b582c32e2942b5747d8db24c48859277394b0f00e8d6f58740  Tracker-Radar-1.0.0-Windows-x64.zip
680635f0c30ef400d59de2c9086bc08efa9d5d50cc19e5a71b556c67465b8487  Tracker-Radar-1.0.0-macOS-Universal.zip
```
