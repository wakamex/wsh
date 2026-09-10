#!/usr/bin/env python3
"""Verify the native neutral-style round-trip fix and repeated editor parity."""
import hashlib
import json
import subprocess
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
evidence = root / 'benchmarks/zsh-highlight-none-2026-09-10'
identity = json.loads((evidence / 'identity.json').read_text())
archive = evidence / 'evidence.tar.gz'
assert identity['selected'] is True
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
for name, digest in identity['current_sources'].items():
    current = (root / name).read_bytes()
    if hashlib.sha256(current).hexdigest() != digest:
        current = subprocess.check_output(['git', 'show', 'ab1691cb6b8245002e2fd03c6aab3cd2628ea6c4:' + name], cwd=root)
    assert hashlib.sha256(current).hexdigest() == digest, name
with tarfile.open(archive) as t:
    for name, digest in identity['files'].items():
        assert hashlib.sha256(t.extractfile(name).read()).hexdigest() == digest, name
    def read(name):
        return json.load(t.extractfile(name))
    before = read('roundtrip-before-final/results.json')
    assert len(before) == 5 and sum(r['correct'] for r in before) == 1
    for directory in ('roundtrip-normal-final', 'roundtrip-sanitized-final', 'floor-checks/highlight-roundtrip'):
        rows = read(directory + '/results.json')
        assert len(rows) == 5 and all(r['correct'] and r['first'] == r['second'] == r['expected'] for r in rows)
    for directory in ('contracts', 'floor-checks/contracts'):
        rows = read(directory + '/results.json')
        assert len(rows) == 9 and all(r['status'] == 0 for r in rows)
    for log in ('observer-before-measure.log', 'observer-fixed-measure.log'):
        assert b'AssertionError' in t.extractfile(log).read()
    rows = read('observer-patched/measure.json')['workloads']
    assert set(rows) == {'short', 'repeated', 'distinct', 'multiline'}
    assert all(r['equal'] and len(r['pairs']) == 50 and r['regions']['control'] == r['regions']['candidate'] for r in rows.values())
    for log in ('build.log', 'floor-build.log'):
        assert b'75 successful test scripts, 0 failures, 2 skipped' in t.extractfile(log).read()
    assert b'PASS: real RPM agreement' in t.extractfile('floor.log').read()
    for log in ('roundtrip-normal-final.log', 'roundtrip-sanitized-final.log'):
        data = t.extractfile(log).read()
        assert b'AddressSanitizer' not in data and b'runtime error:' not in data
print('PASS: Zsh neutral-style memo/layer round trips, repeated redraws and canonical floor')
