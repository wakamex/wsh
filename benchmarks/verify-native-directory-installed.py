#!/usr/bin/env python3
"""Recompute installed directory adoption gates from retained raw evidence."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import tarfile
root = Path(__file__).resolve().parent/'native-directory-final-2026-09-10'
identity = json.loads((root/'installed-identity.json').read_text())
archive = root/'installed.tar.gz'
assert identity['selected'] is True
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
with tarfile.open(archive) as t:
    def read(name):
        return json.load(t.extractfile(name))
    for path, digest in identity['source'].items():
        assert hashlib.sha256(t.extractfile(path).read()).hexdigest() == digest
    rows = read('directory-compiled-contracts/results.json')
    assert len(rows) == 9 and all(r['status'] == 0 for r in rows)
    rows = read('directory-installed-normal/results.json')
    assert len(rows) == 6 and all(r['status'] == 0 for r in rows)
    for prefix in ('directory-installed-normal/query', 'directory-installed-san-query'):
        rows = read(prefix+'/results.json')
        assert len(rows) == 720 and all(r['equal'] and r['results'][0] == r['results'][1] for r in rows)
    for prefix in ('directory-installed-normal/confirmation', 'directory-installed-san-confirmation'):
        rows = read(prefix+'/results.json')
        assert len(rows) == 8
        assert all(r['prompted'] and r['lock_status'] == 0 for r in rows if r['action'] != 'no-tty')
    rows = read('directory-installed-san-mount/results.json')
    assert len(rows) == 2 and all(r['inode_preserved'] for r in rows)
    assert all((r['database'] == r['before']) == r['readonly'] for r in rows)
    summary = read('directory-installed-cost/summary.json')
    assert set(summary) == {'100/lookup','100/write','1000/lookup','1000/write'}
    for name, row in summary.items():
        pairs = row['pairs']
        assert len(pairs) == 50
        medians = {owner: statistics.median(p[owner] for p in pairs) for owner in ('control','candidate')}
        assert medians == row['median_ms']
        delta = sorted(p['candidate']-p['control'] for p in pairs)[47]
        assert math.isclose(delta, row['paired_p95_delta_ms'], abs_tol=1e-9)
        if name.endswith('lookup'):
            assert 1-medians['candidate']/medians['control'] >= .2
        else:
            assert delta <= 3
    samples = read('directory-startup/samples.json')
    summary = read('directory-startup/summary.json')
    assert len(samples) == 200
    for theme, row in summary.items():
        data = {v:[s['readiness_ms'] for s in samples if s['theme'] == theme and s['variant'] == v] for v in ('control','native')}
        assert all(len(v) == 50 for v in data.values())
        delta = sorted(n-c for n,c in zip(data['native'],data['control']))[47]
        assert math.isclose(delta, row['paired_p95_ms'], abs_tol=1e-9) and delta <= 3
print('PASS: installed native directory correctness, identity, command and startup gates')
