#!/usr/bin/env python3
"""Verify the retained real offline source-RPM and Fedora login qualification."""
import hashlib
import io
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
evidence = root/'benchmarks/source-rpm-2026-09-11'
identity = json.loads((evidence/'identity.json').read_text())
archive = (evidence/'results.tar.gz').read_bytes()
assert hashlib.sha256(archive).hexdigest() == identity['archive_sha256']
with tarfile.open(fileobj=io.BytesIO(archive)) as t:
    files = {m.name:t.extractfile(m).read() for m in t.getmembers()}
assert set(files) == set(identity['files'])
for name,data in files.items():
    assert hashlib.sha256(data).hexdigest() == identity['files'][name], name
assert files['source/wsh.tar.gz'] == files['source/wsh-repeat.tar.gz']
# The source archive preserves the actual historical inputs, independently of
# later working-tree changes to the build recipe or tests.
with tarfile.open(fileobj=io.BytesIO(files['source/wsh.tar.gz'])) as t:
    source = {m.name.split('/',1)[1]:t.extractfile(m).read() for m in t.getmembers()}
metadata = json.loads(source['source-info.json'])
for name,digest in metadata['files'].items():
    assert hashlib.sha256(source[name]).hexdigest() == digest, name
log = files['rebuild.log']
for marker in (b'PASS: real SRPM sources, dependencies', b'PASS: source RPM final installed payload and complete native checks', b'find-debuginfo: done'):
    assert marker in log, marker
assert log.count(b'A01grammar.ztst: all tests successful.') == 2
assert b'Cannot stat:' not in log
queries = json.loads(files['rpm-queries.json'])
assert len(queries) == 3
paths = next(v['--list'] for k,v in queries.items() if k.startswith('wsh-debugsource-'))
assert any(p.endswith('/Src/wsh-startup.c') for p in paths)
assert any(p.endswith('/Src/exec.c') for p in paths)
result = json.loads(files['vm/result.json'])
assert result == dict(install=True,inventory=True,chsh=True,pam_logins=3,job_control=3,reboot=True,removal_guard=True,removal=True)
for name in ('empty-home-login','theme-login','post-reboot-login'):
    result = json.loads(files['vm/'+name+'.json'])
    assert result['pam_tty_login'] and result['job_control']
    assert b'JOB_STATUS:130' in files['vm/'+name+'.bin']
assert files['vm/boot-before.log'] != files['vm/boot-after.log']
assert b'Enforcing' in files['vm/install.log'] and b'Enforcing' in files['vm/final-removal.log']
print('PASS: source-only RPM, offline Fedora rebuild, upstream/native checks, complete debug sources and three QEMU PAM/job-control logins')
