"""Fail packaging when the actual executable has the wrong architecture."""
from pathlib import Path
import platform
import struct
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
label = sys.argv[1]
if label == 'macOS-Universal':
    bundle = root / 'dist/Tracker Radar.app'
    executable = bundle / 'Contents/MacOS/Tracker Radar'
    checked = 0
    for path in bundle.rglob('*'):
        if not path.is_file() or path.is_symlink():
            continue
        kind = subprocess.check_output(['file', '-b', str(path)], text=True)
        if 'Mach-O' in kind:
            archs = subprocess.check_output(['lipo', '-archs', str(path)], text=True).split()
            assert {'arm64', 'x86_64'} <= set(archs), f'Not Universal: {path}: {archs}'
            checked += 1
    assert checked > 0
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(bundle)], check=True)
    print(f'Verified {checked} Universal Mach-O files')
elif label == 'Windows-x64':
    executable = root / 'dist/Tracker Radar/Tracker Radar.exe'
    with executable.open('rb') as stream:
        assert stream.read(2) == b'MZ'
        stream.seek(0x3c)
        offset = struct.unpack('<I', stream.read(4))[0]
        stream.seek(offset)
        assert stream.read(4) == b'PE\0\0'
        assert struct.unpack('<H', stream.read(2))[0] == 0x8664, 'Expected x64 PE'
elif label == 'Linux-x64':
    executable = root / 'dist/Tracker Radar/Tracker Radar'
    with executable.open('rb') as stream:
        header = stream.read(20)
    assert header[:6] == b'\x7fELF\x02\x01', 'Expected ELF64 little-endian'
    assert struct.unpack('<H', header[18:20])[0] == 62, 'Expected x86-64 ELF'
else:
    raise SystemExit('Unsupported platform label')
print(f'Architecture verified: {label} (test host: {platform.machine()})')
