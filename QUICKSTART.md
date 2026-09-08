# Tracker Radar 1.0.0 · BinaryBears · MIT

Open Tracker Radar. No Python installation is needed.

On Windows and Linux, extract the whole archive first and keep the executable with its bundled files. On macOS, open the DMG, drag Tracker Radar to Applications, then launch it from Applications.

1. Click **Load list** to fetch the ngosang presets, or import your own `.txt`.
2. Optionally add a magnet or `.torrent` to query seeders and peers.
3. Click **Test trackers**.
4. Optionally exclude zero seeders, zero peers, or both. The count shows how many trackers will be kept.
5. **Copy clean list** or **Save TXT** exports that exact selection. The original input is unchanged.

Double-click a row for details. Review means the tracker needs attention, not that it is dead. Failed means the test failed from this connection; try again before excluding it permanently. Unknown swarm statistics are shown as a dash, not zero. With seed/peer filters enabled, unknown counts are excluded unless you select Keep unknown / review. Untested, failed and invalid entries are never exported.

The app contacts trackers directly. No content is downloaded, but trackers can see your IP and the requested torrent hash. Private torrent files are restricted to their embedded trackers; use the original `.torrent` for private swarms. Treat exported passkeys as credentials.

Signing and notarization status is stated in each GitHub release. Release DMGs and their apps are Developer ID signed and Apple notarized. Ordinary CI ZIPs use ad-hoc signatures; Windows builds are unsigned. A fresh download can trigger the operating system's security checks; a locally passing test does not establish warning-free public distribution.

Linux x64 packages built on Debian 12 require glibc 2.36+ and X11/XWayland. Windows packages are x64. macOS packages are Universal (Apple Silicon and Intel).

Source code: MIT License, copyright 2026 BinaryBears LLC. Included LICENSE applies to application code; dependencies retain their own licenses. List source: https://github.com/ngosang/trackerslist
