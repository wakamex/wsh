#!/usr/bin/env python3
"""Verify exact directory takeover, preserved lifecycle and matched startup gates."""
import hashlib
import json
from pathlib import Path
import tarfile
import subprocess

root = Path(__file__).resolve().parents[1]
evidence = root / 'benchmarks/native-directory-takeover-2026-09-10'
identity = json.loads((evidence / 'identity.json').read_text())
for name, digest in identity['sources'].items():
    current = (root / name).read_bytes()
    if hashlib.sha256(current).hexdigest() != digest:
        current = subprocess.check_output(['git', 'show', '7bbee20:' + name], cwd=root)
    assert hashlib.sha256(current).hexdigest() == digest, name
archive = evidence / 'evidence.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
with tarfile.open(archive) as t:
    for name, digest in identity['files'].items():
        assert hashlib.sha256(t.extractfile(name).read()).hexdigest() == digest, name
    def read(name):
        return json.load(t.extractfile(name))
    contracts = read('contracts-final/results.json')
    assert len(contracts) == 9 and all(r['status'] == 0 for r in contracts)
    for name in ('contracts-final/directory-jump.log', 'floor-final.log'):
        log = t.extractfile(name).read()
        for case in ('builtin', 'external', 'legacy-completion', 'modified', 'override', 'custom-alias', 'custom-command', 'removed', 'disabled-external', 'custom', 'executable', 'disabled'):
            assert ('PASS: ' + case + ' directory-jump ownership and behavior').encode() in log, (name, case)
        assert b'PASS: real ZLE completion handles spaces and prompt hooks record directory visits' in log
        assert b'PASS: directory database persists across Wsh sessions' in log
    rows = read('engine/results.json')
    assert len(rows) == 10 and all(r['exact_equal'] for r in rows if r['name'] != 'tab')
    samples = read('startup-final/samples.json')
    summary = read('startup-final/summary.json')
    assert len(samples) == 200
    for theme, row in summary.items():
        data = {v: [s['readiness_ms'] for s in samples if s['theme'] == theme and s['variant'] == v] for v in ('control', 'native')}
        assert len(data['control']) == len(data['native']) == row['pairs'] == 50
        delta = sorted(data['native'][i] - data['control'][i] for i in range(50))[47]
        assert delta == row['paired_p95_ms'] <= row['gate_ms'] == 3
        assert row['passed']
        assert sorted(data['control'])[24] == row['control_median_ms']
        assert sorted(data['native'])[24] == row['native_median_ms']
print('PASS: recognized directory takeover, preserved state/customization/completion and startup gates')
