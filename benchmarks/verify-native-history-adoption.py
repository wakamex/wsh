#!/usr/bin/env python3
"""Verify installed history ownership, editor parity and fixed performance gates."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import tarfile

out = Path(__file__).resolve().parents[1] / 'benchmarks/native-adoption-2026-09-10/history'
for line in (out/'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert hashlib.sha256((out/name).read_bytes()).hexdigest() == digest
identity = json.loads((out/'identity.json').read_text())
with tarfile.open(out/'inputs.tar.gz') as archive:
    for name,digest in identity['input_sha256'].items():
        assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest, name
with tarfile.open(out/'results.tar.gz') as archive:
    def read(name):
        return json.load(archive.extractfile(name))
    for name in ('history-installed','history-installed-sanitized-expanded'):
        rows = read(name+'/results/correctness.json')
        assert len(rows) == 10
        assert all(r['equal'] and r['variants'][0] == r['variants'][1] and len(r['variants'][0]) == 11 for r in rows)
    summary = read('history-installed/results/summary.json')
    assert len(summary) == 4
    for row in summary.values():
        pairs = row['pairs']
        assert len(pairs) == 50
        for owner in ('control','candidate'):
            assert all(math.isfinite(p[owner]) and p[owner] > 0 for p in pairs)
            assert row['median_ms'][owner] == statistics.median(p[owner] for p in pairs)
        delta = sorted(p['candidate']-p['control'] for p in pairs)[47]
        assert row['paired_p95_delta_ms'] == delta and delta <= 1
        assert math.isclose(row['median_reduction'],1-row['median_ms']['candidate']/row['median_ms']['control'])
    assert summary['10000/unique=True']['median_reduction'] >= .20
    samples = read('history-startup/samples.json')
    summary = read('history-startup/summary.json')
    assert len(samples) == 200
    for theme in ('existing','minimal'):
        groups = {v:[r['readiness_ms'] for r in samples if r['theme']==theme and r['variant']==v] for v in ('control','native')}
        assert all(len(v)==50 for v in groups.values())
        delta = sorted(n-c for n,c in zip(groups['native'],groups['control']))[47]
        assert summary[theme]['paired_p95_ms'] == delta and delta <= 3
        assert summary[theme]['passed'] and summary[theme]['gate_ms'] == 3
print('PASS: native history input identities, 110 editor comparisons and installed editing/startup gates')
