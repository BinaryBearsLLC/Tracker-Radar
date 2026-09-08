#!/bin/bash
# Same release gates as ntfsmac: signed app -> notarize/staple -> signed DMG -> notarize/staple.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
: "${MACOS_SIGN_IDENTITY:?Set an authorized Developer ID Application identity}"
: "${NOTARY_PROFILE:?Set an existing notarytool Keychain profile}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
notary_args=(--keychain-profile "$NOTARY_PROFILE")
if [[ -n "${SIGNING_KEYCHAIN:-}" ]]; then
  notary_args+=(--keychain "$SIGNING_KEYCHAIN")
fi
version="$($PYTHON_BIN -c 'from tracker_core import APP_VERSION; print(APP_VERSION)')"
app='dist/Tracker Radar.app'
dmg="dist/packages/Tracker-Radar-${version}-macOS-Universal.dmg"
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
codesign --verify --deep --strict "$app"
ditto -c -k --keepParent "$app" "$work/application.zip"
xcrun notarytool submit "$work/application.zip" "${notary_args[@]}" --wait --output-format json > "$work/app-status.json"
"$PYTHON_BIN" -c 'import json,sys; assert json.load(open(sys.argv[1]))["status"] == "Accepted", "App notarization rejected"' "$work/app-status.json"
xcrun stapler staple "$app"
xcrun stapler validate "$app"
"$PYTHON_BIN" scripts/make_dmg.py
xcrun notarytool submit "$dmg" "${notary_args[@]}" --wait --output-format json > "$work/dmg-status.json"
"$PYTHON_BIN" -c 'import json,sys; assert json.load(open(sys.argv[1]))["status"] == "Accepted", "DMG notarization rejected"' "$work/dmg-status.json"
xcrun stapler staple "$dmg"
xcrun stapler validate "$dmg"
codesign --verify --deep --strict "$app"
codesign --verify --strict "$dmg"
spctl --assess --type execute --verbose=2 "$app"
spctl --assess --type open --context context:primary-signature --verbose=2 "$dmg"
shasum -a 256 "$dmg"
echo 'App and DMG accepted, stapled, signature-checked and Gatekeeper-approved.'
