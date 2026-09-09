#!/usr/bin/env python3
"""Verify native floor, complete artifact reproduction and installed VM evidence."""
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-qualification-2026-09-09'
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
for line in (OUT / 'floor-SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest
meta = json.loads((OUT / 'floor-metadata.json').read_text())
with tarfile.open(OUT / 'floor-inputs.tar.gz') as a:
    for name, digest in meta['source_inputs'].items():
        assert sha(a.extractfile(name).read()) == digest
    for rpm in meta['sdk_packages']:
        assert sha(a.extractfile('sdk-rpms/'+rpm['file']).read()) == rpm['sha256']
with tarfile.open(OUT / 'floor-results.tar.gz') as a:
    def raw(name):
        return a.extractfile(name).read()
    def data(name):
        return json.loads(raw(name))
    results = data('reproduction-results.json')
    assert results['passed'] and results['source_revision'] == meta['built_source_revision']
    assert results['builds']['a'] == results['builds']['b']
    build = results['builds']['a']
    assert sha(raw('native.tar.xz')) == build['archive_sha256']
    assert sha(raw('native.rpm')) == build['rpm_sha256']
    with tarfile.open(fileobj=io.BytesIO(raw('native.tar.xz'))) as payload:
        files = {}
        for entry in payload.getmembers():
            if entry.isfile():
                name = entry.name.split('/', 1)[1]
                files[name] = sha(payload.extractfile(entry).read())
        assert files == build['files']
        assert files['manifest.json'] == build['manifest_sha256']
        assert files['bin/wsh'] == build['shell_sha256']
        assert files['bin/wsh-runtime'] == build['helper_sha256']
    checks = data('contracts/results.json')
    assert len(checks) == 9 and all(r['status'] == 0 for r in checks)
    checks = data('extra/results.json')
    assert len(checks) == 8 and all(r['status'] == 0 for r in checks)
    for elf in data('floor-elf.json'):
        versions = sorted(set(re.findall(r'Name: GLIBC_([0-9.]+)', elf['readelf_version_info'])), key=lambda s: tuple(map(int, s.split('.'))))
        assert versions == elf['glibc_versions']
        assert tuple(map(int, versions[-1].split('.'))) <= (2, 28)
    for name in ('a','b'):
        assert raw('build-'+name+'-floor.log').rstrip().endswith(build['manifest_sha256'].encode())
    assert b'PASS: relocated development bundle' in raw('canonical-legacy-floor.log')
    assert b'newest imported symbol GLIBC_2.28' in raw('canonical-legacy-floor.log')
    assert b'Permission denied' in raw('build-b-selinux-conflict.log')
    assert b'command not found: python3' in raw('build-a-missing-python.log')
    for case in ('floor-package-pam','floor-package-confined','floor-package-post-reboot-pam','floor-package-post-reboot-confined'):
        assert data('vm/'+case+'.json')['pam_tty_login']
    assert data('vm/floor-package-pam.json')['job_control']
    assert len(data('vm/recovery-results.json')) == 7
    assert all(r['pam_tty_login'] for r in data('vm/recovery-results.json'))
    assert b'Enforcing' in raw('vm/floor-package-post-reboot.log')
    boot_ids = re.findall(rb'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', raw('vm/floor-package-reboot.log'))
    assert boot_ids and boot_ids[-1] != raw('vm/floor-package-post-reboot.log').splitlines()[0]
print('PASS: native floor contracts, independent complete artifacts, canonical legacy suite and installed RPM login')
