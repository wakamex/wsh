#!/usr/bin/env python3
"""Verify exact traversal parity and retain its failed complete-redraw gates."""
import hashlib
import json
from pathlib import Path
import statistics
import tarfile

root = Path(__file__).resolve().parents[1]
evidence = root / 'benchmarks/native-highlighting-traversal-2026-09-10'
identity = json.loads((evidence / 'identity.json').read_text())
archive = evidence / 'evidence.tar.gz'
assert identity['selected'] is False
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
for name, digest in identity['current_sources'].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
with tarfile.open(archive) as t:
    for name, digest in identity['files'].items():
        data = t.extractfile(name).read()
        assert hashlib.sha256(data).hexdigest() == digest, name
        if name.startswith(('corpus-patched-sanitized/', 'corpus-patched-sanitized-final/')) and name.endswith('.log'):
            assert b'AddressSanitizer' not in data and b'runtime error:' not in data, name
    def read(name):
        return json.load(t.extractfile(name))
    for directory in ('corpus', 'sanitized-corpus', 'corpus-patched', 'corpus-patched-sanitized', 'corpus-patched-sanitized-final'):
        rows = read(directory + '/results.json')
        assert len(rows) == 574 and all(r['passed'] for r in rows)
        for owner in ('control', 'candidate'):
            assert len({r['case'] for r in rows if r['owner'] == owner}) == 287
    for directory in ('zle', 'zle-sanitized-final', 'zle-sanitized-formatted'):
        rows = read(directory + '/correctness.json')['workloads']
        assert len(rows) == 4 and all(r['equal'] and r['regions']['control'] == r['regions']['candidate'] for r in rows.values())
    for directory in ('zle', 'observer-overhead'):
        rows = read(directory + '/measure.json')['workloads']
        assert len(rows) == 4
        for name, row in rows.items():
            pairs = row['pairs']
            assert len(pairs) == 50 and row['equal']
            assert row['regions']['control'] == row['regions']['candidate']
            medians = {o: statistics.median(p[o] for p in pairs) for o in ('control', 'candidate')}
            assert medians == row['median_ms']
            reduction = 1 - medians['candidate'] / medians['control']
            delta = sorted(p['candidate'] - p['control'] for p in pairs)[47]
            assert reduction == row['median_reduction'] and delta == row['paired_p95_delta_ms']
            if directory == 'zle':
                assert reduction < .2
                if name in ('repeated', 'distinct'):
                    assert delta > 1
print('PASS: native traversal exact parity and retained failed redraw improvement/regression gates')
