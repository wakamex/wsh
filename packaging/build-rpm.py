#!/usr/bin/env python3
"""Assemble an unsigned experimental RPM from a verified native development payload."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('installation', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--release', default='0.1')
parser.add_argument('--fault', choices=('none', 'pre', 'post', 'pause'), default='none')
args = parser.parse_args()
assert all(c in '0123456789.' for c in args.release) and args.release
bundle = args.installation.resolve()
top = args.output.resolve()
manifest = json.loads((bundle / 'manifest.json').read_text())
assert manifest['status'] == 'development'
for entry in manifest['files']:
    path = bundle / entry['path']
    assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], entry['path']
assert (bundle / 'bin/wsh').is_file() and not (bundle / 'zdotdir').exists()
for name in ('SOURCES', 'SPECS', 'BUILD', 'BUILDROOT', 'RPMS', 'SRPMS'):
    (top / name).mkdir(parents=True, exist_ok=True)
with tarfile.open(top / 'SOURCES/native-payload.tar.gz', 'w:gz') as archive:
    archive.add(bundle, arcname='payload')
subprocess.run(['rpmbuild', '-bb', '--define', '_topdir ' + str(top), '--define', 'wsh_release ' + args.release,
                '--define', 'wsh_fault ' + args.fault, str(ROOT / 'packaging/wsh-native.spec')], check=True)
for path in sorted((top / 'RPMS').rglob('*.rpm')):
    print(path)
