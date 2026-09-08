# Repository instructions

Read `README.md`, inspect git status and preserve user changes. Work from this self-contained repository. Keep documentation concise: update the README instead of adding separate guides or audit reports. `RELEASE_NOTES.md` is consumed by release automation; preserve dependency license texts.

## Scope and invariants

- Desktop Python/Tk GUI only, English, compact flat styling and BinaryBears branding. No web-app rewrite, telemetry, accounts, content downloads or unrelated features.
- Require a valid protocol response, not DNS/open-port/HTTP-200 evidence. Match scrape counters to the exact hash; unknown is not zero. Never sum trackers as unique swarm totals.
- Preserve raw torrent `info` hashing and private-torrent routing to embedded trackers. No discovered-peer connections or DHT. Announce fallback stays stopped with `numwant=0`.
- Clean filters preserve the source list. Failed/invalid/untested entries cannot be exported; review is opt-in and zero filters require torrent context.
- Network work stays off the GUI thread. Stop/close must terminate workers.

## Validation and release

- Run the README's tests, GUI harness and packaged smoke tests. Check import, filters, clipboard, saved TXT and stop/retest; distinguish fixtures, live network, emulation and native desktop evidence. Do not claim unperformed visual checks.
- Windows builds require actual x64 PE verification. Mac Universal builds require Universal Python/Tk, all Mach-O architectures verified, and ARM/Intel smoke (Rosetta allowed). Linux requires glibc 2.36+ and X11/XWayland.
- Mac releases use the branded DMG, Developer ID signing, Apple notarization and stapling of both app and DMG, plus Gatekeeper verification. Use existing authorized credentials; never request secrets in chat or commit them.
- Keep exactly three public packages: Mac Universal DMG, Windows x64 ZIP, Linux x64 TAR.GZ. Do not weaken signing or security checks. Windows remains unsigned unless separately configured.
- Version lives in `tracker_core.py`; synchronize website and release notes when changing it. Rebuild changed application source, never relabel old binaries. Verify the public download separately.
- Push, tagging and publication require user authorization. GitHub is `BinaryBearsLLC/Tracker-Radar`; Pages deploys `site/` from `main`.
- Keep caches, local paths and credentials out of Git. Historical 3.1.0 binaries in ignored `prebuilt/` are not current source and must not be deleted without explicit authorization.
