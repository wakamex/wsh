#!/usr/bin/env python3
"""Verify retained real public-login and compiled build-status qualification."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

root = Path(__file__).resolve().parents[1]
evidence = root/'benchmarks/release-fixes-2026-09-10'
login = json.loads((evidence/'public-login.json').read_text())
for name, digest in login['sources'].items():
    data = (root/name).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        data = subprocess.check_output(['git','show','37e8d0a:'+name],cwd=root)
    assert hashlib.sha256(data).hexdigest() == digest, name
log = (evidence/'public-login.log').read_bytes()
assert hashlib.sha256(log).hexdigest() == login['log_sha256']
assert log.rstrip().endswith(b'WSH_LOGIN_OK') and b'Installing util-linux' in log
identity = json.loads((evidence/'version-status.json').read_text())
for name, digest in identity['sources'].items():
    data = (root/name).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        data = subprocess.check_output(['git','show','13cb60d:'+name],cwd=root)
    assert hashlib.sha256(data).hexdigest() == digest, name
archive = evidence/'version-status.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
with tarfile.open(archive) as t:
    for name,digest in identity['files'].items():
        assert hashlib.sha256(t.extractfile(name).read()).hexdigest() == digest, name
    for name in ('build-status-installed.log','build-status-floor.log'):
        assert t.extractfile(name).read().startswith(b'PASS: compiled development/release labels')
    assert b'PASS: installed label' in t.extractfile('build-status-installed.log').read()
    manifest = json.load(t.extractfile('manifest.json'))
    assert manifest['status'] == 'development'
    assert next(r['sha256'] for r in manifest['files'] if r['path']=='bin/wsh') == identity['binary_sha256']
    assert b'unsigned development artifact' in t.extractfile('version.txt').read()
print('PASS: real Fedora public RPM login, compiled build-mode isolation and installed native version qualification')
