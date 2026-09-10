#!/usr/bin/env python3
"""Verify complete native main-highlighter parity, lifetime and paired timing."""
import hashlib
import json
from pathlib import Path
import statistics
import tarfile

root = Path(__file__).resolve().parents[1]
evidence = root / 'benchmarks/native-highlighting-full-2026-09-10'
identity = json.loads((evidence / 'identity.json').read_text())
archive = evidence / 'evidence.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
for name, digest in identity['current_sources'].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
with tarfile.open(archive) as t:
    for name, digest in identity['archive_files'].items():
        data = t.extractfile(name).read()
        assert hashlib.sha256(data).hexdigest() == digest, name
        if name.startswith(('corpus-sanitized-final/', 'differential-sanitized-final/', 'zle-sanitized-final/')) and name.endswith(('.log', '.stderr', '.pty')):
            assert b'AddressSanitizer' not in data and b'runtime error:' not in data, name
    def read(name):
        return json.load(t.extractfile(name))
    for directory in ('corpus-final', 'corpus-sanitized-final'):
        rows = read(directory + '/results.json')
        assert len(rows) == 574 and all(r['passed'] for r in rows)
        for owner in ('control', 'candidate'):
            assert len({r['case'] for r in rows if r['owner'] == owner}) == 287
    for directory in ('differential-final', 'differential-sanitized-final'):
        rows = read(directory + '/results.json')
        assert len(rows) == 3360 and all(r['equal'] and r['control'] == r['candidate'] for r in rows)
        assert read(directory + '/summary.json')['input_executed'] is False
    for directory in ('zle-final', 'zle-sanitized-final'):
        rows = read(directory + '/correctness.json')['workloads']
        assert len(rows) == 4 and all(r['equal'] and r['regions']['control'] == r['regions']['candidate'] for r in rows.values())
    identical = read('identical-measured/measure.json')['workloads']
    for directory in ('zle-final', 'identical-measured', 'capture-measured'):
        rows = read(directory + '/measure.json')['workloads']
        assert len(rows) == 4
        for name, row in rows.items():
            pairs = row['pairs']
            assert len(pairs) == 50 and row['equal'] and row['regions']['control'] == row['regions']['candidate']
            medians = {o: statistics.median(p[o] for p in pairs) for o in ('control', 'candidate')}
            assert medians == row['median_ms']
            reduction = 1 - medians['candidate'] / medians['control']
            delta = sorted(p['candidate'] - p['control'] for p in pairs)[47]
            assert reduction == row['median_reduction'] and delta == row['paired_p95_delta_ms']
            if directory == 'zle-final':
                assert medians['candidate'] - medians['control'] <= max(.5, medians['control'] * .05)
                assert delta <= max(1, identical[name]['paired_p95_delta_ms'])
    before = read('lifetime-before/result.json')
    after = read('lifetime-fixed/result.json')
    assert before['retained_growth_kib'] > before['maximum_growth_kib']
    assert after['retained_growth_kib'] <= after['maximum_growth_kib'] == 8192
    candidate = t.extractfile('fixture-3/candidate/highlighters/main/main-highlighter.zsh').read()
    assert b'_zsh_highlight_main_highlighter_highlight_list' not in candidate
    assert b'builtin wsh-highlight-main' in candidate
    native = t.extractfile('source/native/highlight-full-prototype.c').read()
    assert b'doshfunc(' not in native and b'execstring(' not in native
print('PASS: complete native main parser, 287 fixtures, 3360 prefixes, sanitizers, lifetime and paired redraw gates')
