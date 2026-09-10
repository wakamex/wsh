#!/usr/bin/env python3
"""Verify combined native and legacy floor qualification evidence."""
import hashlib
import json
from pathlib import Path
import re
import tarfile
root = Path(__file__).resolve().parent/'native-directory-final-2026-09-10'
identity = json.loads((root/'floor-identity.json').read_text())
archive = root/'floor.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
assert all(identity[k] == 0 for k in ('native_build_status','native_tests_status','canonical_status'))
with tarfile.open(archive) as t:
    def read(name):
        return json.load(t.extractfile(name))
    for name, digest in identity['source'].items():
        assert hashlib.sha256(t.extractfile('inputs/'+name).read()).hexdigest() == digest
    command = read('native-command.json')
    assert 'WSH_SOURCE_REVISION='+identity['source_revision'] in command
    assert read('native-build-status.json') == {'revision':identity['source_revision'],'status':0}
    rows = read('qualification/results.json')
    assert len(rows) == 17 and all(r['status'] == 0 for r in rows)
    rows = read('qualification/contracts/results.json')
    assert len(rows) == 9 and all(r['status'] == 0 for r in rows)
    rows = read('qualification/completion/correctness-results.json')
    assert len(rows) == 5 and all(r['status'] == 0 for r in rows)
    rows = read('qualification/history/results/correctness.json')
    assert len(rows) == 10 and all(len(r['variants'][0]) == 11 and r['variants'][0] == r['variants'][1] for r in rows)
    rows = read('qualification/directory-query/results.json')
    assert len(rows) == 720 and all(r['equal'] and r['results'][0] == r['results'][1] for r in rows)
    rows = read('startup/startup-results.json')
    assert len(rows) == 14 == identity['startup_scope']['floor_cases']
    rows = read('bind-mount/results.json')
    assert len(rows) == 2 and all(r['inode_preserved'] for r in rows)
    for row in rows:
        assert row['status'] == int(row['readonly'])
        assert (row['database'] == row['before']) == row['readonly']
    for row in read('native-elf.json').values():
        versions = sorted(set(re.findall(r'Name: GLIBC_([0-9.]+)',row['version_info'])),key=lambda s:tuple(map(int,s.split('.'))))
        assert versions == row['glibc_versions']
        assert tuple(map(int,versions[-1].split('.'))) <= (2,28)
    for kind in ('native','legacy'):
        data = t.extractfile(kind+'-manifest.json').read()
        assert hashlib.sha256(data).hexdigest() == identity[kind+'_bundle']
        manifest = json.loads(data)
        assert manifest['status'] == 'development' and manifest['requirements']['minimum_glibc'] == '2.28'
    log = t.extractfile('legacy-build.log').read().decode()
    assert 'PASS: relocated development bundle '+identity['legacy_bundle']+' on glibc floor; newest imported symbol GLIBC_2.28' in log
print('PASS: combined native and canonical legacy glibc 2.28 qualification')
