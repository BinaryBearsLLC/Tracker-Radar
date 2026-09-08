# Tracker Radar 1.0.0 — verification

## Local checks — 8 September 2026

- Original local 3.1.0 archives: all three SHA-256 hashes passed before changes; archives remain unchanged in ignored `prebuilt/`.
- Source: 47 unittest checks passed, including local HTTP/UDP protocol fixtures, hash accuracy, private routing, worker cancellation, clean filters and new cross-origin redirect protections.
- Real Tk control harness: minimum size, TXT import, magnet/torrent parsing, private routing, response display, both zero filters, clipboard contents, saved TXT contents, original-list preservation, stop/retest and list-load cancellation passed. Native file dialogs are stubbed in this harness.
- macOS: new Universal build with local Python 3.13.14/Tk; ARM64 and x86_64 (Rosetta) packaged smoke passed. All 54 Mach-O files include both architectures. Strict/deep Developer ID signature verification passed. Notarization is not established.
- Linux: new x64 package built with Python 3.13.15 in Debian 12 under Docker x64 emulation on Apple Silicon. Tests and packaged Xvfb smoke passed; ELF x86-64 architecture confirmed. Native hosted evidence is recorded separately below.
- Live network: valid UDP reply from tracker.opentrackr.org and valid HTTPS scrape response from torrent.ubuntu.com. Ubuntu's HTTP endpoint attempted a cross-origin redirect and was blocked. Availability observations are time/connection specific, not permanent uptime guarantees.
- Website: static assets, internal anchors, English language, three versioned download links and checksum link validated. Desktop light/dark screenshots inspected; responsive and theme interaction checks use a real Chromium browser.

## Hosted checks

Pending first push: the three-platform workflow and Pages workflow must pass before this section is updated with run links. No local result should be treated as a hosted success.

## Limits

A smoke test verifies startup, Tk, the bundled runtime and spawned worker/result queue. It is not a full manual desktop test. Physical Windows x64 and Intel Mac visual QA, full screen-reader testing, Windows Authenticode signing, macOS notarization and testing every supported OS version are not established. Linux requires glibc 2.36+ and a graphical X11/XWayland session.

The website's app screenshot uses labelled demonstration data. No fixture counts are presented as live swarm data. Tracker counters are never unique totals across trackers.
