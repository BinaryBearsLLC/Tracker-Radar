"""Require exactly three version-matched archives before publishing."""
import hashlib
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracker_core import APP_VERSION

folder = Path(sys.argv[1])
assert os.environ['RELEASE_TAG'] == f'v{APP_VERSION}', 'Tag/source version mismatch'
expected = {f'Tracker-Radar-{APP_VERSION}-{label}{ext}' for label, ext in (
    ('macOS-Universal', '.zip'), ('Windows-x64', '.zip'), ('Linux-x64', '.tar.gz'))}
actual = {p.name for p in folder.iterdir()}
assert actual == expected, f'Unexpected release assets: {actual ^ expected}'
lines = []
for name in sorted(expected):
    with (folder / name).open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    lines.append(f'{digest}  {name}\n')
(folder / 'SHA256SUMS.txt').write_text(''.join(lines), encoding='utf-8')
print('Verified three version-matched platform archives; wrote SHA256SUMS.txt')
