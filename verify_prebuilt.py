"""Verify the three unchanged release archives. Python standard library only."""
import hashlib
from pathlib import Path
import sys

EXPECTED = {
    'Tracker-Radar-3.1.0-macOS-Universal.zip': '3042e2996a7f2dd6b9561aa48635a038234765bb9d20b65bdad41da6902718d0',
    'Tracker-Radar-3.1.0-Windows-x64.zip': 'f62d79c08c05386ce0f5b6b8659275a7239ea11a5fa2f6d3f710dc3d73077481',
    'Tracker-Radar-3.1.0-Linux-x64.tar.gz': '11933d1770307bd26e3dbfc678014100382fa8ca1c7f34f42d6708c86a452b4e',
}


def main():
    folder = Path(__file__).resolve().parent / 'prebuilt'
    actual = {p.name for p in folder.iterdir() if p.is_file()} if folder.is_dir() else set()
    if actual != set(EXPECTED):
        print('Unexpected or missing packages:', sorted(actual.symmetric_difference(EXPECTED)))
        return 1
    for name, expected in EXPECTED.items():
        with (folder / name).open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != expected:
            print('FAIL:', name)
            return 1
        print('OK:', name)
    return 0


if __name__ == '__main__':
    sys.exit(main())
