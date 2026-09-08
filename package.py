"""Portable native archives; preserve executable modes on Unix."""
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import shutil
import zipfile
from tracker_core import APP_VERSION

root = Path(__file__).resolve().parent
label = sys.argv[1]
expected = {"darwin": "macOS-Universal", "win32": "Windows-x64"}.get(sys.platform, "Linux-x64")
if label != expected:
    raise SystemExit(f"This host must produce {expected}, not {label}")
subprocess.run([sys.executable, str(root / "scripts/verify_native.py"), label], check=True)
out = root / "dist" / "packages"
out.mkdir(exist_ok=True)
name = "Tracker-Radar-" + APP_VERSION + "-" + label
if sys.platform == "darwin":
    with tempfile.TemporaryDirectory(prefix="tracker-radar-package-") as temporary:
        stage = Path(temporary) / "Tracker Radar"
        stage.mkdir()
        shutil.copytree(root / "dist/Tracker Radar.app", stage / "Tracker Radar.app", symlinks=True)
        for filename in ("Start Tracker Radar.command", "QUICKSTART.md", "THIRD_PARTY_NOTICES.md", "LICENSE"):
            shutil.copy2(root / filename, stage / filename)
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
                        str(stage), str(out / (name + ".zip"))], check=True)
elif sys.platform == "win32":
    shutil.copy2(root / "LICENSE", root / "dist/Tracker Radar/LICENSE")
    shutil.copy2(root / "QUICKSTART.md", root / "dist/Tracker Radar/QUICKSTART.md")
    shutil.copy2(root / "THIRD_PARTY_NOTICES.md", root / "dist/Tracker Radar/THIRD_PARTY_NOTICES.md")
    with zipfile.ZipFile(out / (name + ".zip"), "w", zipfile.ZIP_DEFLATED) as archive:
        for path in (root / "dist/Tracker Radar").rglob("*"):
            archive.write(path, path.relative_to(root / "dist"))
else:
    shutil.copy2(root / "LICENSE", root / "dist/Tracker Radar/LICENSE")
    shutil.copy2(root / "QUICKSTART.md", root / "dist/Tracker Radar/QUICKSTART.md")
    shutil.copy2(root / "THIRD_PARTY_NOTICES.md", root / "dist/Tracker Radar/THIRD_PARTY_NOTICES.md")
    with tarfile.open(out / (name + ".tar.gz"), "w:gz") as archive:
        archive.add(root / "dist/Tracker Radar", arcname="Tracker Radar")
