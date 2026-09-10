#!/usr/bin/env python3
"""Verify installed controller evidence, including rejected independent results."""
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import tarfile

root = Path(__file__).resolve().parents[1]
evidence = root / 'benchmarks/native-autosuggestions-installed-2026-09-10'
identity = json.loads((evidence / 'identity.json').read_text())
archive = evidence / 'evidence.tar.gz'
assert identity['selected'] is True
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
for name, digest in identity['current_sources'].items():
    data = (root / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        data = subprocess.check_output(['git', 'show', 'c78fbf44bcb90ba97ab8e8c9fb3515ec8d182e84:' + name], cwd=root)
    assert hashlib.sha256(data).hexdigest() == digest, name
with tarfile.open(archive) as t:
    for name, digest in identity['files'].items():
        data = t.extractfile(name).read()
        assert hashlib.sha256(data).hexdigest() == digest, name
        if name in ('sanitized-correctness.log', 'sanitized-lifecycle.log', 'sanitized-bounds.log'):
            assert b'PASS:' in data and b'AddressSanitizer' not in data and b'runtime error:' not in data
    def read(name):
        return json.load(t.extractfile(name))
    for directory in ('correctness', 'sanitized-correctness', 'floor-checks/autosuggestions'):
        rows = read(directory + '/correctness.json')
        assert len(rows) == 10 and all(r['equal'] and r['variants'][0] == r['variants'][1] for r in rows)
    for directory in ('lifecycle', 'sanitized-lifecycle', 'floor-checks/autosuggestions-lifecycle'):
        row = read(directory + '/lifecycle.json')
        assert all(row[k] is True for k in ('ctrl_c_prompt', 'fd_cleared', 'child_reaped'))
    for directory in ('bounds', 'sanitized-bounds', 'floor-checks/autosuggestions-bounds'):
        row = read(directory + '/bounds.json')
        assert row['discarded'] and row['fd_cleared'] and row['response_bytes'] > row['limit_bytes'] == 1048576
    for directory in ('contracts-final', 'floor-checks/contracts'):
        rows = read(directory + '/results.json')
        assert len(rows) == 9 and all(r['status'] == 0 for r in rows)
    rows = read('omz-final/results.json')
    assert len(rows) == 5 and all(r['passed'] and r['doctor_status'] == 0 for r in rows)
    for case in ('pending', 'automatic'):
        assert b'\x1eWIDGET:user:_zsh_autosuggest_bound_' in t.extractfile('omz-final/' + case + '/transcript.bin').read()
    for count, row in read('measure/summary.json').items():
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
    samples = read('startup/samples.json')
    assert len(samples) == 200
    for theme, row in read('startup/summary.json').items():
        selected = [s for s in samples if s['theme'] == theme]
        values = {owner: {s['pair']: s['readiness_ms'] for s in selected if s['variant'] == owner} for owner in ('control', 'native')}
        assert all(set(v) == set(range(50)) for v in values.values())
        delta = sorted(values['native'][i] - values['control'][i] for i in range(50))[47]
        assert delta == row['paired_p95_ms'] and delta <= row['gate_ms'] == 3 and row['passed']
    assert b'PASS: real RPM agreement' in t.extractfile('floor.log').read()
    assert b'75 successful test scripts, 0 failures, 2 skipped' in t.extractfile('floor-build.log').read()
    assert all(r['status'] == 1 and r['timeout'] for r in read('doctor-tty-counterfactual.json'))
    assert all(r['status'] == 1 for r in read('sanitized-Y06.json'))
    assert len(read('sanitized-upstream-counterfactual.json')) == 4
    assert all(r['status'] == 1 for r in read('sanitized-upstream-counterfactual.json'))
print('PASS: installed native autosuggestions, ownership, sanitizers, paired editing/startup and canonical floor')
