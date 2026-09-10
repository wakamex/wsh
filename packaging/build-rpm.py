#!/usr/bin/env python3
"""Assemble an unsigned experimental RPM from a verified native development payload."""
import argparse
import hashlib
import gzip
import os
import json
from pathlib import Path
import subprocess
import tarfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"build"))
from native_manifest import verify

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('installation', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--release', default='0.1')
parser.add_argument('--epoch', type=int, help='reproducible artifact timestamp; defaults to source commit time')
parser.add_argument('--fault', choices=('none', 'pre', 'post', 'pause'), default='none')
args = parser.parse_args()
assert all(c in '0123456789.' for c in args.release) and args.release
bundle = args.installation.resolve()
top = args.output.resolve()
manifest = verify(bundle)
assert manifest['status'] == 'development' or args.fault == 'none'
assert (bundle / 'bin/wsh').is_file() and not (bundle / 'zdotdir').exists()
for name in ('SOURCES', 'SPECS', 'BUILD', 'BUILDROOT', 'RPMS', 'SRPMS'):
    (top / name).mkdir(parents=True, exist_ok=True)
epoch = args.epoch if args.epoch is not None else int(subprocess.check_output(
    ['git', 'show', '-s', '--format=%ct', 'HEAD'], cwd=ROOT, text=True).strip())
assert 0 <= epoch <= 0xffffffff, 'epoch must fit a gzip timestamp'
def normalize(info):
    info.uid = info.gid = 0
    info.uname = info.gname = ''
    info.mtime = epoch
    info.mode = 0o755 if info.isdir() or info.name.startswith('payload/bin/') else 0o644
    return info
with (top / 'SOURCES/native-payload.tar.gz').open('wb') as output:
    with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=epoch) as compressed:
        with tarfile.open(fileobj=compressed, mode='w', format=tarfile.GNU_FORMAT) as archive:
            archive.add(bundle, arcname='payload', filter=normalize)
subprocess.run(['rpmbuild', '-bb', '--define', '_topdir ' + str(top), '--define', 'wsh_release ' + args.release, '--define', 'wsh_version ' + manifest['version'],
                '--define', 'dist %{nil}',
                '--define', 'wsh_fault ' + args.fault,
                '--define', '_buildhost wsh-development',
                '--define', 'use_source_date_epoch_as_buildtime 1',
                '--define', 'clamp_mtime_to_source_date_epoch 1',
                str(ROOT / 'packaging/wsh-native.spec')], check=True,
               env=dict(os.environ, SOURCE_DATE_EPOCH=str(epoch), TZ='UTC', LC_ALL='C'))
for path in sorted((top / 'RPMS').rglob('*.rpm')):
    print(path)
