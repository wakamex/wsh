#!/usr/bin/env python3
"""Verify the live upstream monitor qualification and workflow inputs."""
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
evidence = root/'benchmarks/plugin-upstreams-2026-09-10'
identity = json.loads((evidence/'identity.json').read_text())
for name, digest in identity['sources'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest() == digest, name
archive = evidence/'evidence.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
entries = json.loads((root/'third_party/plugin-catalog/catalog.json').read_text())['entries']
upstreams = json.loads((root/'third_party/plugin-catalog/upstreams.json').read_text())['upstreams']
with tarfile.open(archive) as t:
    for name, digest in identity['files'].items():
        assert hashlib.sha256(t.extractfile(name).read()).hexdigest() == digest, name
    rows = json.load(t.extractfile('results.json'))
    assert len(rows) == len(upstreams) == 6
    for row, upstream in zip(rows, upstreams):
        assert row['status'] == 'known'
        assert all(row[k] == upstream[k] for k in ('component','repository','branch'))
        assert [f['path'] for f in row['files']] == upstream['paths']
        digests = [f['sha256'] for f in row['files']]
        matches = [e for e in entries if e['component'] == row['component'] and e['repository'] == row['repository'] and [f['upstream_path'] for f in e['files']] == upstream['paths']]
        assert any([f['sha256'] for f in e['files']] == digests for e in matches)
        for digest in digests:
            assert hashlib.sha256(t.extractfile(digest).read()).hexdigest() == digest
    assert t.extractfile('tests.log').read().startswith(b'PASS: monitor')
    assert identity['actionlint_status'] == 0 and not t.extractfile('actionlint.log').read()
print('PASS: daily monitor live GitHub file identities, catalog matches and workflow qualification')
