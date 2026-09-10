#!/usr/bin/env python3
"""Verify retained private controller correctness and complete-sequence timing."""
import hashlib
import json
from pathlib import Path
import statistics
import tarfile

root = Path(__file__).resolve().parents[1]
evidence = root / 'benchmarks/native-consolidation-2026-09-10'
identity = json.loads((evidence / 'autosuggestions-identity.json').read_text())
archive = evidence / 'autosuggestions-evidence.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
assert identity['selected'] is False
with tarfile.open(archive) as t:
    for name, digest in identity['files'].items():
        assert hashlib.sha256(t.extractfile(name).read()).hexdigest() == digest, name
    def read(name):
        return json.load(t.extractfile(name))
    for directory in ('suggestion-qualified', 'suggestion-qualified-sanitized'):
        rows = read(directory + '/correctness.json')
        assert len(rows) == 10 and all(r['equal'] for r in rows)
        assert all(r['variants'][0] == r['variants'][1] for r in rows)
        markers = read(directory + '/widget-names.json')
        assert not markers['candidate'] and markers['control']
    for directory in ('suggestion-lifecycle-final', 'suggestion-lifecycle-sanitized'):
        result = read(directory + '/lifecycle.json')
        assert all(result[k] is True for k in ('ctrl_c_prompt', 'fd_cleared', 'child_reaped'))
        before = read(directory + '/before-cancel.json')
        assert before['pid'] == before['pgid'] == result['pid']
    bounds = read('suggestion-bounds/bounds.json')
    assert bounds['response_bytes'] > bounds['limit_bytes'] == 1048576
    assert bounds['discarded'] and bounds['fd_cleared']
    summary = read('suggestion-final-measure/summary.json')
    assert set(summary) == {'100', '10000'}
    for count, row in summary.items():
        pairs = row['pairs']
        assert len(pairs) == 50
        medians = {owner: statistics.median(p[owner] for p in pairs) for owner in ('control', 'candidate')}
        assert medians == row['median_ms']
        delta = sorted(p['candidate'] - p['control'] for p in pairs)[47]
        assert delta == row['paired_p95_delta_ms'] and delta <= 1
        reduction = 1 - medians['candidate'] / medians['control']
        assert reduction == row['median_reduction']
        if count == '10000':
            assert reduction >= .2
print('PASS: complete autosuggestion prototype parity, lifecycle, response bound and paired timing')
