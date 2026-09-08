"""Build on the target OS: python build.py. No cross-compilation."""
import os
from pathlib import Path
import platform
import plistlib
import subprocess
import sys
from tracker_core import APP_VERSION

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--windowed", "--onedir", "--name", "Tracker Radar",
           "--add-data", "assets:assets", "--add-data", "LICENSE:.", "--collect-data", "certifi",
           "--hidden-import", "certifi", "--distpath", "dist", "--workpath", "build"]
if sys.platform == "darwin":
    command += ["--icon", "assets/icon.icns", "--osx-bundle-identifier", "com.binarybears.trackerradar"]
    if os.environ.get("MACOS_TARGET_ARCH"):
        command += ["--target-arch", os.environ["MACOS_TARGET_ARCH"]]
    if os.environ.get("MACOS_SIGN_IDENTITY"):
        command += ["--codesign-identity", os.environ["MACOS_SIGN_IDENTITY"]]
elif sys.platform == "win32":
    command += ["--icon", "assets/icon.ico"]
command += ["tracker_radar.py"]
subprocess.run(command, check=True)
if sys.platform == "darwin":
    bundle = ROOT / "dist/Tracker Radar.app"
    plist_path = bundle / "Contents/Info.plist"
    with plist_path.open("rb") as stream:
        plist = plistlib.load(stream)
    plist.update(CFBundleShortVersionString=APP_VERSION, CFBundleVersion=APP_VERSION,
                 NSHumanReadableCopyright="Copyright 2026 BinaryBears LLC",
                 LSMinimumSystemVersion="11.0", NSHighResolutionCapable=True)
    with plist_path.open("wb") as stream:
        plistlib.dump(plist, stream)
    identity = os.environ.get("MACOS_SIGN_IDENTITY", "-")
    sign = ["codesign", "--force", "--options", "runtime", "--sign", identity]
    if identity != "-":
        sign.append("--timestamp")
    subprocess.run(sign + [str(bundle)], check=True)
print(f"Built for {platform.system()} {platform.machine()}: {ROOT / 'dist'}")
