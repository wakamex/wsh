#!/usr/bin/env python3
"""Verify real collector behavior and matched prompt ownership startup gates."""
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
evidence = root / 'benchmarks/git-prompt-ownership-2026-09-10'
identity = json.loads((evidence / 'identity.json').read_text())
for name, digest in identity['sources'].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
archive = evidence / 'evidence.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
with tarfile.open(archive) as t:
    for name, digest in identity['files'].items():
        assert hashlib.sha256(t.extractfile(name).read()).hexdigest() == digest, name
    def read(name):
        return json.load(t.extractfile(name))
    for name in ('host/results.json', 'floor/results.json'):
        rows = read(name)
        assert len(rows) == 7 and all(r['passed'] for r in rows)
        for row in rows:
            if row['case'] in ('wsh', 'absent'):
                assert row['collector_calls'] == 0 and row['state'].endswith('|0|0|0')
            else:
                assert row['collector_calls'] > 0
    contracts = read('contracts/results.json')
    assert len(contracts) == 9 and all(r['status'] == 0 for r in contracts)
    samples = read('startup/samples.json')
    summary = read('startup/summary.json')
    assert len(samples) == 200
    for theme, row in summary.items():
        data = {v: [s['readiness_ms'] for s in samples if s['theme'] == theme and s['variant'] == v] for v in ('control', 'native')}
        assert len(data['control']) == len(data['native']) == row['pairs'] == 50
        delta = sorted(data['native'][i] - data['control'][i] for i in range(50))[47]
        assert delta == row['paired_p95_ms'] <= row['gate_ms'] == 3
        assert row['passed']
        assert sorted(data['control'])[24] == row['control_median_ms']
        assert sorted(data['native'])[24] == row['native_median_ms']
print('PASS: exact git-prompt hook ownership, real collector, fallback, custom hooks and startup gates')
