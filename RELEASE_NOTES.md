First public release of Tracker Radar by BinaryBears.

Load tracker lists from TXT, paste, URL or ngosang presets. Test UDP, HTTP and HTTPS directly, optionally query a magnet or torrent, then copy or save a clean list with zero-seeder and zero-peer filters. Private torrent files use only their embedded trackers. No DHT, peer connections, content downloads or telemetry.

Download one archive for your platform and extract it completely. Python is bundled.

- **macOS Universal:** macOS 11+, Apple Silicon and Intel. Automated builds are ad-hoc signed, not notarized. Gatekeeper may block a downloaded app; no security checks are disabled by the installer.
- **Windows x64:** Windows 10+, Intel/AMD 64-bit. Unsigned; SmartScreen may warn.
- **Linux x64:** glibc 2.36+, X11/XWayland. Built on Debian 12.

The release workflow runs protocol tests, source GUI smoke, packaged GUI/worker smoke and executable architecture checks before publishing all three archives. macOS includes an Intel smoke under Rosetta. Linux uses Xvfb. These checks do not establish full physical-desktop QA or compatibility with every supported OS version.

Use SHA256SUMS.txt to check downloaded archives. Source and bundled dependencies retain their respective licenses; see THIRD_PARTY_NOTICES.md.
