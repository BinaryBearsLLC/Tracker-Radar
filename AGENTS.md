# Instructions for the next coding agent

## Handoff

This folder is the complete, self-contained starting point for a new repository. The prior project is abandoned: do not depend on its paths, virtual machines, environments or files. Work from this repository root. The current application is Tracker Radar **1.0.0** by **BinaryBears**, open source under **MIT**.

Read `README.md` and `VERIFICATION.md` before changes. Inspect git status and preserve user changes. The GitHub repository is BinaryBearsLLC/Tracker-Radar. Do not push, tag, publish a release or deploy anything without an explicit request. The owner authorized the initial 1.0.0 publication.

## Product scope — keep it small

- Desktop GUI only; English interface, compact flat styling and BinaryBears branding.
- Import tracker lists from local TXT, URL, paste or ngosang presets.
- Check UDP/HTTP/HTTPS directly from the user's computer.
- Optionally query a magnet/torrent against the list; show per-tracker seeders and incomplete peers.
- Clean by failed status, zero seeders and/or zero peers; copy or save the resulting TXT.
- No browser version, Electron/backend rewrite, dashboards, telemetry, accounts, content downloads or unrelated features.
- Preserve the existing runtime-light design. This is Python/Tk, not Qt or a web wrapper.

## Current files

- `tracker_core.py`: protocol engine, bounded parsing, hash handling, privacy routing, clean selection.
- `tracker_radar.py`: GUI and isolated multiprocessing worker.
- `tests/`: 47 tests, including ten clean-selection tests and release safety regressions.
- `build.py`: native PyInstaller build; `package.py`: portable archives.
- `prebuilt/`: exactly three existing **3.1.0** compiled packages. These are real builds, not placeholders. Verify with `python verify_prebuilt.py`.
- `LICENSE`, `assets/licenses/`, `THIRD_PARTY_NOTICES.md`: preserve notices and BinaryBears copyright.

The ignored 3.1.0 archives are historical baseline binaries and no longer match current source. Do not publish them as 1.0.0. Rebuild, retest and update package names/checksums for every delivery. Application version lives in `tracker_core.py`; GUI branding reads that constant. Update the website, release notes and docs with it.

## First commands

```sh
git status --short
python --version
python verify_prebuilt.py
python -m venv .venv
```

If Python or Tk is absent, explain/install the required development dependencies with approval before global host changes. Do not weaken execution policies or security checks to make setup easier. No PowerShell bypass is needed: invoke `.venv\Scripts\python.exe` directly if activation is restricted.

### macOS/Linux development

```sh
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python tracker_radar.py --smoke-test
.venv/bin/python tracker_radar.py
```

### Windows development (PowerShell)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tracker_radar.py --smoke-test
.\.venv\Scripts\python.exe build.py
$p = Start-Process -FilePath '.\dist\Tracker Radar\Tracker Radar.exe' -ArgumentList '--smoke-test' -PassThru -Wait
if ($p.ExitCode -ne 0) { throw 'Packaged smoke test failed' }
.\.venv\Scripts\python.exe package.py Windows-x64
```

Use an x64 Python interpreter for the Windows x64 package. The host OS architecture string can report ARM64 under emulation even when the executable is x64; inspect the actual PE architecture.

### macOS Universal package

Use universal2 Python/Tk and universal-compatible dependencies. Do not assume every interpreter installed by a CI setup action is universal.

```sh
MACOS_TARGET_ARCH=universal2 .venv/bin/python build.py
'dist/Tracker Radar.app/Contents/MacOS/Tracker Radar' --smoke-test
arch -x86_64 'dist/Tracker Radar.app/Contents/MacOS/Tracker Radar' --smoke-test
.venv/bin/python package.py macOS-Universal
```

The Intel smoke command requires an Intel host or Rosetta. For a Developer ID build, set `MACOS_SIGN_IDENTITY` to an available authorized identity before invoking `build.py`. The supplied package was signed by `Developer ID Application: BinaryBears LLC (SQY8T23X8N)`. No private key, notarization profile or credential is included. Check with:

```sh
codesign --verify --deep --strict 'dist/Tracker Radar.app'
xcrun stapler validate 'dist/Tracker Radar.app'
```

The historical 3.1.0 Mac package has **no notarization ticket**. Current release automation signs and notarizes both the 1.0.0 app and branded DMG; see `SIGNING.md`. Ask for the name of an already configured notarytool profile if notarization is requested; never ask the owner to paste secrets into chat. Do not claim that a signature alone removes Gatekeeper warnings.

### Linux package

The existing build used Debian 12 x64, Python 3.13.15, Tcl/Tk, binutils, X11, xauth and Xvfb. It requires glibc 2.36+. Use a native x64 environment or explicitly label emulated tests.

```sh
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python build.py
xvfb-run -a 'dist/Tracker Radar/Tracker Radar' --smoke-test
.venv/bin/python package.py Linux-x64
```

## Invariants

- DNS, an open port, HTTP 200 or tracker-like HTML are not sufficient proof of a working tracker.
- Match scrape counters to the exact requested hash. Unknown or missing data is not zero.
- Preserve raw `info` hashing for torrents and private-torrent routing to embedded trackers only.
- Do not register as an active peer, contact discovered peers, use DHT or download payloads. Announce fallback is stopped with `numwant=0`.
- Clean filters must not mutate the source list. Failed/invalid/untested entries are never exported. Unknown/review data is opt-in; zero filters need a torrent context.
- Stop/close must end worker activity. Keep network work off the GUI thread.
- Never sum tracker counts as unique swarm totals.

## Before handoff

Run all tests and packaged smoke tests. Manually check minimum-size layout, TXT import, magnet/torrent parsing, live response display, both clean toggles, clipboard copy, saved TXT contents and stop/retest behavior. Distinguish fixture, live-network, virtual-machine and physical-desktop evidence.

Native Tk controls have a sparse accessibility tree. During previous Mac QA, keyboard traversal and native file dialogs worked where coordinate-based automation failed. Do not silently claim unperformed visual or clipboard checks.

Keep exactly three public platform packages when preparing the next release: Universal Mac, Windows x64, Linux x64. The build workflow has three platform jobs. Version tags publish only after all build jobs pass and the tag/source version and three-asset set match. GitHub Pages deploys site/ from main. Check VERIFICATION.md and actual hosted run results.

Do not include caches, build directories, old versions, source ZIP duplicates, machine-specific paths or credentials in future handoffs. Do not delete the supplied baseline binaries unless explicitly asked; keep them unchanged until a replacement is verified.
