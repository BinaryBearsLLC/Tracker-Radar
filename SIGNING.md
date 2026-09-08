# Release signing

Official Mac releases use a Developer ID Application identity. The app is signed with hardened runtime, submitted to Apple and stapled. The branded drag-to-Applications DMG is then signed, submitted separately and stapled. Both must pass strict signature, notarization-ticket and Gatekeeper checks before publication. The layout and BinaryBears artwork follow the ntfsmac installer.

## GitHub Actions

Configure these repository Actions secrets; never put their values in source files, issues or logs:

| Secret | Value |
| --- | --- |
| `APPLE_CERTIFICATE_P12_BASE64` | Base64 of the exported Developer ID certificate **and private key** |
| `APPLE_CERTIFICATE_PASSWORD` | Password protecting that export |
| `APPLE_SIGNING_IDENTITY` | Full Developer ID Application identity name |
| `APPLE_API_KEY_BASE64` | Base64 of the App Store Connect API `.p8` key |
| `APPLE_API_KEY_ID` | API Key ID |
| `APPLE_API_ISSUER_ID` | App Store Connect API Issuer ID |

The runner imports these into a temporary keychain, validates Apple access, removes the temporary input files, and restores the original keychain list during cleanup. Secret-bearing subprocess arguments are not included in failure messages.

Tag builds require signing credentials and fail if signing or notarization fails. To test the complete path without publishing, manually run **Build and release** on `main` with **signed_macos** enabled. Ordinary push and pull-request builds produce an ad-hoc Mac ZIP for CI testing. Release publication requires exactly one notarized Mac DMG, one Windows x64 ZIP and one Linux x64 TAR.GZ.

## Local Mac release

Use an already configured `notarytool` keychain profile and authorized Developer ID identity. Keep credentials outside the checkout. After the Universal app build and both architecture smoke tests:

```sh
.venv/bin/python -m pip install -r requirements-packaging.txt
export MACOS_SIGN_IDENTITY='Developer ID Application: Example Company (TEAMID)'
export NOTARY_PROFILE='release-notary'
# Optional: SIGNING_KEYCHAIN selects the keychain containing the profile.
PYTHON_BIN=.venv/bin/python scripts/notarize_macos.sh
```

`assets/dmg/layout.json` and `scripts/render_dmg.swift` are the editable background source. Regenerate `assets/dmg/background.png` after layout changes. `scripts/make_dmg.py` writes Finder metadata without GUI automation. Never publish its output before the notarization script finishes successfully.

## Windows

Windows packages are currently unsigned. Apple Developer ID certificates cannot authenticate a Windows publisher. Trusted Authenticode signing needs a separate Windows code-signing certificate or a service such as Microsoft Artifact Signing. There is no fallback to a self-signed certificate and no claim that SmartScreen warnings are eliminated.
