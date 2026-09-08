"""Check tracked files (or all reachable Git blobs) without echoing sensitive matches."""
from pathlib import Path
import re
import subprocess
import sys

PATTERNS = {
    'private key material': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'personal macOS home path': re.compile(rb'/Users/(?!runner(?:/|$)|Shared/|build/|<)[A-Za-z0-9_.-]+/'),
    'personal Windows home path': re.compile(rb'[A-Z]:\\Users\\(?!runneradmin\\|Public\\|<)[A-Za-z0-9_.-]+\\'),
    'temporary macOS home path': re.compile(rb'/private/var/folders/[a-z0-9]{2}/[a-z0-9_]+/'),
}
PRIVATE_SUFFIXES = {'.p8', '.p12', '.pfx', '.pem', '.key', '.keychain', '.keychain-db', '.env'}


def main():
    findings = []
    history = '--history' in sys.argv
    if history:
        objects = subprocess.check_output(['git', 'rev-list', '--objects', '--all'], text=True).splitlines()
        entries = []
        for obj in objects:
            oid, _, name = obj.partition(' ')
            if name and subprocess.check_output(['git', 'cat-file', '-t', oid]).strip() == b'blob':
                entries.append((name, subprocess.check_output(['git', 'cat-file', 'blob', oid])))
    else:
        entries = [(name, Path(name).read_bytes()) for name in subprocess.check_output(['git', 'ls-files', '-z']).decode().split('\0') if name]
    for name, data in entries:
        if Path(name).suffix.lower() in PRIVATE_SUFFIXES:
            findings.append((name, 'private configuration or signing filename'))
        for label, pattern in PATTERNS.items():
            if pattern.search(data):
                findings.append((name, label))
    for name, label in sorted(set(findings)):
        print(f'FAIL {name}: {label} (matched value redacted)')
    print(f'Privacy audit: {len(entries)} file revisions checked, {len(set(findings))} findings')
    return bool(findings)


if __name__ == '__main__':
    sys.exit(main())
