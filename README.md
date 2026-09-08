# Tracker Radar

Desktop BitTorrent tracker diagnostics by **BinaryBears**. Version **1.0.0**, MIT licensed. Python/Tk, English interface, no installation of Python required.

[Website](https://binarybearsllc.github.io/Tracker-Radar/) · [Downloads and checksums](https://github.com/BinaryBearsLLC/Tracker-Radar/releases/latest)

![Tracker Radar desktop interface](site/assets/app.png)

## Install and use

| Platform | Package | Requirements |
| --- | --- | --- |
| macOS Universal | Signed, notarized DMG | macOS 11+, Apple Silicon or Intel |
| Windows x64 | Unsigned portable ZIP | Windows 10+, Intel/AMD 64-bit |
| Linux x64 | TAR.GZ | glibc 2.36+, X11/XWayland |

On macOS, open the DMG and drag Tracker Radar to Applications. On Windows and Linux, extract the entire archive and run Tracker Radar, keeping its bundled files together. Windows SmartScreen may warn because the executable is unsigned. To uninstall, remove the app or extracted folder.

1. Load a tracker list from TXT, URL, paste or an ngosang preset.
2. Optionally add a magnet or `.torrent` to query per-tracker seeders and incomplete peers.
3. Test UDP, HTTP and HTTPS directly from your connection.
4. Exclude zero seeders and/or peers if needed, then **Copy clean list** or **Save TXT**.

A valid BitTorrent response establishes a working tracker; an open port or HTTP 200 alone does not. Unknown statistics are not zero. Review is opt-in; failed, invalid and untested entries never enter clean exports. The original list is preserved. Never add tracker counts as unique swarm totals.

Private torrents use only embedded trackers; cross-origin tracker redirects are blocked. Magnets cannot reliably identify private torrents. Trackers see your IP and queried hash. There is no telemetry, account, backend, DHT, peer connection or content download.

## Development and packaging

Use Python 3.13 with Tk and build on the target operating system:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python tracker_radar.py --smoke-test
.venv/bin/python scripts/gui_qa.py
.venv/bin/python build.py
.venv/bin/python package.py macOS-Universal
```

On Windows, invoke `.venv\Scripts\python.exe` directly and use package label `Windows-x64`; no execution-policy changes are needed. On Linux, use `Linux-x64` and prefix headless GUI commands with `xvfb-run -a`. `package.py` checks executable architecture. A Universal Mac build requires Universal Python/Tk and `MACOS_TARGET_ARCH=universal2`. Test its executable normally and with `arch -x86_64` (Intel or Rosetta).

For a signed Mac build, set `MACOS_SIGN_IDENTITY` before running `build.py`. Then install `requirements-packaging.txt`, set `NOTARY_PROFILE` to an existing notarytool profile, and run:

```sh
PYTHON_BIN=.venv/bin/python scripts/notarize_macos.sh
```

Optional `SIGNING_KEYCHAIN` selects the profile's keychain. The script signs/verifies, notarizes and staples the app and branded DMG separately, then checks Gatekeeper. Keep credentials outside the checkout. DMG artwork and layout live in `assets/dmg/`; regenerate `background.png` with `scripts/render_dmg.swift` after visual changes.

## Actions and releases

The build workflow tests macOS Universal, Windows x64 and Linux x64. Tags require these encrypted repository secrets:

| Secret | Contents |
| --- | --- |
| `APPLE_CERTIFICATE_P12_BASE64` | Base64 Developer ID certificate and private-key export |
| `APPLE_CERTIFICATE_PASSWORD` | Export password |
| `APPLE_SIGNING_IDENTITY` | Full Developer ID Application identity |
| `APPLE_API_KEY_BASE64` | Base64 App Store Connect API `.p8` key |
| `APPLE_API_KEY_ID` | API Key ID |
| `APPLE_API_ISSUER_ID` | API Issuer ID |

Signing uses a temporary keychain and cleans up afterward. Manual **signed_macos** builds test notarization without publishing; ordinary CI builds produce an ad-hoc Mac ZIP. A `v*` tag publishes exactly three packages only after all platform jobs, version checks and signing gates pass. Update `APP_VERSION`, website links and `RELEASE_NOTES.md`, test locally, then commit and push an authorized version tag. Pages deploys `site/`; privacy CI scans tracked files and Git history. Action dependencies and downloaded build tools are pinned.

## Verification

For 1.0.0, all 47 tests, Tk control checks, packaged smoke tests and architecture checks passed on all three [CI targets](https://github.com/BinaryBearsLLC/Tracker-Radar/actions/runs/34227294438). Mac Intel smoke uses Rosetta; Linux uses Debian 12 with Xvfb. Local GUI checks covered import, private routing, both filters, clipboard, saved TXT and stop/retest; the harness stubs file dialogs, with an additional native Mac import check. Website light/dark/auto and mobile layouts were checked.

The public Mac DMG contains the tagged application source built locally with Python 3.13.14; Windows and Linux are the original tagged CI artifacts. The downloaded DMG passed checksum, app/container signature, stapled-ticket, Gatekeeper and ARM/Intel smoke checks. Checksums are in the release's `SHA256SUMS.txt`. Repository/history and public-artifact/log scans found no owner personal paths or credentials. Corporate attribution and third-party runtime metadata remain public.

These checks do not establish physical Windows/Intel Mac visual QA, full screen-reader support or every OS version. Historical 3.1.0 packages remain unchanged in ignored `prebuilt/`; `verify_prebuilt.py` checks them when present.

## License

Copyright 2026 BinaryBears LLC. Application code is MIT licensed. Keep [LICENSE](LICENSE), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and the full [dependency licenses](assets/licenses/) with distributions. Optional presets come from [ngosang/trackerslist](https://github.com/ngosang/trackerslist).
