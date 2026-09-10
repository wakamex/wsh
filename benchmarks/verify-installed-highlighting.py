#!/usr/bin/env python3
"""Verify selected main highlighting, installed contracts and canonical evidence."""
import hashlib
import json
from pathlib import Path
import statistics
import tarfile

root = Path(__file__).resolve().parents[1]
evidence = root / 'benchmarks/native-highlighting-installed-2026-09-10'
identity = json.loads((evidence / 'identity.json').read_text())
assert identity['selected'] is True
assert identity['normal_binary_sha256'] == identity['corpus_binary_sha256']
archive = evidence / 'evidence.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
for name, digest in identity['current_sources'].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
with tarfile.open(archive) as t:
    for name, digest in identity['archive_files'].items():
        data = t.extractfile(name).read()
        assert hashlib.sha256(data).hexdigest() == digest, name
        if name.startswith(('installed-sanitized-corpus/', 'installed-sanitized-prefixes/', 'installed-sanitized-editor/')) and name.endswith(('.log', '.stderr', '.pty')):
            assert b'AddressSanitizer' not in data and b'runtime error:' not in data, name
    def read(name):
        return json.load(t.extractfile(name))
    for directory in ('installed-corpus', 'installed-sanitized-corpus'):
        rows = read(directory + '/results.json')
        assert len(rows) == 574 and all(r['passed'] for r in rows)
        for owner in ('control', 'candidate'):
            assert len({r['case'] for r in rows if r['owner'] == owner}) == 287
    for directory in ('installed-highlighting-qualified/prefixes', 'installed-sanitized-prefixes', 'floor-checks/highlighting/prefixes'):
        rows = read(directory + '/results.json')
        assert len(rows) == 3360 and all(r['equal'] and r['control'] == r['candidate'] for r in rows)
        assert read(directory + '/summary.json')['input_executed'] is False
    for directory in ('installed-highlighting-qualified/editor', 'installed-sanitized-editor', 'floor-checks/highlighting/editor'):
        rows = read(directory + '/correctness.json')['workloads']
        assert len(rows) == 4 and all(r['equal'] and r['regions']['control'] == r['regions']['candidate'] for r in rows.values())
    for directory in ('installed-highlighting-qualified/lifetime', 'floor-checks/highlighting/lifetime'):
        data = read(directory + '/result.json')
        assert data['redraws_per_batch'] == 2000
        assert data['retained_growth_kib'] == data['rss_kib'][-1] - data['rss_kib'][0]
        assert data['retained_growth_kib'] <= data['maximum_growth_kib'] == 8192
    for directory in ('installed-contracts-qualified', 'floor-checks/contracts'):
        rows = read(directory + '/results.json')
        assert len(rows) == 9 and all(r['status'] == 0 for r in rows)
    rows = read('installed-highlighting-qualified/editor/measure.json')['workloads']
    assert len(rows) == 4
    for row in rows.values():
        pairs = row['pairs']
        assert len(pairs) == 50 and row['equal'] and row['regions']['control'] == row['regions']['candidate']
        medians = {o: statistics.median(p[o] for p in pairs) for o in ('control', 'candidate')}
        assert medians == row['median_ms']
        assert 1 - medians['candidate'] / medians['control'] == row['median_reduction']
        delta = sorted(p['candidate'] - p['control'] for p in pairs)[47]
        assert delta == row['paired_p95_delta_ms']
        assert medians['candidate'] - medians['control'] <= max(.5, medians['control'] * .05)
        assert delta <= 1
    samples = read('installed-startup/samples.json')
    summary = read('installed-startup/summary.json')
    assert len(samples) == 200
    for theme, row in summary.items():
        data = {v: [r['readiness_ms'] for r in samples if r['theme'] == theme and r['variant'] == v] for v in ('control', 'native')}
        assert len(data['control']) == len(data['native']) == 50
        assert sorted(data['control'])[24] == row['control_median_ms']
        assert sorted(data['native'])[24] == row['native_median_ms']
        assert sorted(data['native'][i]-data['control'][i] for i in range(50))[47] == row['paired_p95_ms']
        assert row['passed'] and row['paired_p95_ms'] <= row['gate_ms'] == 3
    for name in ('normal', 'floor'):
        adapter = t.extractfile(name + '/main/main-highlighter.zsh').read()
        original = t.extractfile(name + '/main/known-main-highlighter.zsh').read()
        assert b'builtin wsh-highlight-main' in adapter
        assert b'_zsh_highlight_main_highlighter_highlight_list' not in adapter
        assert original == (root / 'third_party/zsh-syntax-highlighting/highlighters/main/main-highlighter.zsh').read_bytes()
    for name in ('logs/installed-build-2.log', 'logs/floor-build.log'):
        log = t.extractfile(name).read()
        assert b'75 successful test scripts, 0 failures, 2 skipped' in log
    assert b'PASS: real RPM agreement' in t.extractfile('logs/floor.log').read()
print('PASS: installed C main highlighting, exact ownership/styles, sanitizers, lifetime, editing/startup and canonical floor')
