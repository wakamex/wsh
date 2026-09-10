#!/usr/bin/env python3
"""Verify older upstream takeover, editor parity and matched startup evidence."""
import difflib
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
evidence = root / 'benchmarks/native-autosuggestions-older-2026-09-10'
identity = json.loads((evidence / 'identity.json').read_text())
for name, digest in identity['sources'].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
vendor = root / 'third_party/zsh-autosuggestions'
diff = ''.join(difflib.unified_diff(
    (vendor / 'known-0.7.0.zsh').read_text().splitlines(True),
    (vendor / 'zsh-autosuggestions.zsh').read_text().splitlines(True),
    fromfile='upstream-v0.7.0', tofile='upstream-v0.7.1'))
assert diff == (evidence / 'upstream.diff').read_text()
archive = evidence / 'evidence.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
with tarfile.open(archive) as t:
    for name, digest in identity['files'].items():
        assert hashlib.sha256(t.extractfile(name).read()).hexdigest() == digest, name

    def read(name):
        return json.load(t.extractfile(name))

    contracts = read('contracts/results.json')
    assert len(contracts) == 9 and all(r['status'] == 0 for r in contracts)
    for name in ('contracts/autosuggestions.log', 'floor.log'):
        assert b'PASS: autosuggestion display, acceptance, ownership, configuration, composition, custom widgets, and cancellation' in t.extractfile(name).read()
    rows = read('omz-final/results.json')
    expected = {
        'pending': 'wsh|1|1', 'automatic': 'wsh|1|1',
        'active': 'external-active|0|1', 'modified': 'external-unknown|0|1',
        'disabled': 'disabled|0|1', 'custom': 'wsh|1|1',
    }
    assert len(rows) == 11 and len({r['case'] for r in rows}) == 11
    for row in rows:
        mode = row['case'].removeprefix('older-')
        assert row['state'] == expected[mode] and row['doctor_status'] == 0 and row['passed']
    editor = read('correctness/correctness.json')
    assert len(editor) == 10 and all(r['equal'] and r['variants'][0] == r['variants'][1] for r in editor)
    lifecycle = read('lifecycle/lifecycle.json')
    assert all(lifecycle[k] for k in ('ctrl_c_prompt', 'fd_cleared', 'child_reaped'))
    bounds = read('bounds/bounds.json')
    assert bounds['response_bytes'] > bounds['limit_bytes'] == 1048576
    assert bounds['discarded'] and bounds['fd_cleared']
    user = read('user/result.json')
    assert user['states']['wsh'][1] == 'wsh' and user['states']['zsh'][1] == 'external'
    assert user['suggestion_display_and_acceptance'] and user['startup_files_unchanged']
    samples = read('startup/samples.json')
    summary = read('startup/summary.json')
    assert len(samples) == 200 and set(summary) == {'existing', 'minimal'}
    for theme, row in summary.items():
        data = {v: [s['readiness_ms'] for s in samples if s['theme'] == theme and s['variant'] == v] for v in ('control', 'native')}
        assert len(data['control']) == len(data['native']) == row['pairs'] == 50
        delta = sorted(data['native'][i] - data['control'][i] for i in range(50))[47]
        assert delta == row['paired_p95_ms'] <= row['gate_ms'] == 3
        assert row['passed']
        assert sorted(data['control'])[24] == row['control_median_ms']
        assert sorted(data['native'])[24] == row['native_median_ms']
print('PASS: older autosuggestion ownership, editor parity, lifecycle, custom strategies and startup gates')
