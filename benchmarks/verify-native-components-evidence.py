#!/usr/bin/env python3
"""Verify the five bounded component experiments and their explicit decisions."""
import hashlib
import json
import math
from pathlib import Path
import shlex
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-components-2026-09-10'
for line in (OUT / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    path = OUT / name
    assert path.resolve().is_relative_to(OUT.resolve())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name

def read(name):
    return json.loads((OUT / name).read_text())

def close(actual, expected):
    assert math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-8), (actual, expected)

def paired(summary):
    for row in summary.values():
        pairs = row['pairs']
        assert len(pairs) == 50
        assert all(set(p) == {'control', 'candidate'} and all(math.isfinite(v) and v > 0 for v in p.values()) for p in pairs)
        medians = {owner: statistics.median(p[owner] for p in pairs) for owner in ('control', 'candidate')}
        for owner in medians:
            close(row['median_ms'][owner], medians[owner])
        close(row['paired_p95_delta_ms'], sorted(p['candidate'] - p['control'] for p in pairs)[47])
        close(row['median_reduction'], 1 - medians['candidate'] / medians['control'])

for run in ('directory-query-final', 'directory-query-sanitized'):
    rows = read(run + '/results.json')
    assert len(rows) == 720
    assert all(r['equal'] and r['results'][0] == r['results'][1] and all(v['status'] == 0 and not v['stderr'] for v in r['results']) for r in rows)
for run in ('directory-mutations', 'directory-sanitized'):
    rows = read(run + '/results.json')
    assert len(rows) == 10 and sum(not r['exact_equal'] for r in rows) == 5
    assert all(r['exact_equal'] == (r['variants'][0] == r['variants'][1]) for r in rows)
    by_name = {r['name']: r for r in rows}
    for name in ('duplicate', 'home-relative'):
        assert not by_name[name]['exact_equal']
for run in ('history-first', 'history-sanitized'):
    rows = read(run + '/results.json')
    assert len(rows) == 32
    assert all(r['equal'] and r['variants'][0] == r['variants'][1] and all(v['status'] == 0 and not v['stderr'] for v in r['variants']) for r in rows)
    assert all(len(bytes.fromhex(r['variants'][0]['stdout']).splitlines()) == 105 for r in rows)
for run in ('history-zle', 'history-zle-sanitized'):
    rows = read(run + '/correctness.json')
    assert len(rows) == 4 and all(r['equal'] and r['variants'][0] == r['variants'][1] and len(r['variants'][0]) == 8 for r in rows)
history = read('history-zle/summary.json')
paired(history)
assert all(r['paired_p95_delta_ms'] <= 1 for r in history.values())
assert history['10000/unique=True']['median_reduction'] >= .20
for run in ('suggestion-final', 'suggestion-sanitized'):
    rows = read(run + '/correctness.json')
    assert {r['mode'] for r in rows} == {'sync', 'async', 'vi', 'custom', 'completion'}
    assert all(r['equal'] and r['variants'][0] == r['variants'][1] for r in rows)
suggestion = read('suggestion-final/summary.json')
paired(suggestion)
assert all(r['paired_p95_delta_ms'] <= 1 for r in suggestion.values())
assert suggestion['10000']['median_reduction'] < .20

with tarfile.open(OUT / 'completion-results.tar.gz') as archive:
    def data(name):
        return json.load(archive.extractfile(name))
    for prefix in ('completion', 'completion-scan'):
        for suffix in ('', '-sanitized'):
            rows = data(prefix + '-dumps' + suffix + '/results.json')
            assert len(rows) == 9 and all(r['passed'] for r in rows)
            rows = data(prefix + '-zle' + suffix + '/correctness.json')
            assert len(rows) == 13 and all(r['passed'] for r in rows)
        rows = data(prefix + '-zle/samples.json')
        summary = data(prefix + '-zle/summary.json')
        assert len(rows) == 450 and len(summary) == 9
        for variant, s in summary.items():
            values = [r for r in rows if r['variant'] == variant]
            assert {r['pair'] for r in values} == set(range(50))
            for field in ('startup_ms',) if variant == 'baseline' else ('startup_ms', 'first_tab_ms', 'second_tab_ms'):
                assert all(math.isfinite(r[field]) and r[field] > 0 for r in values)
                close(s[field], sorted(r[field] for r in values)[47])
            if variant != 'baseline':
                overhead = s['startup_ms'] - summary['baseline']['startup_ms']
                limit = 20 if variant.endswith('-warm') else 100
                close(s['startup_overhead_ms'], overhead)
                assert s['startup_limit_ms'] == limit
                assert s['passed'] == (overhead <= limit and s['first_tab_ms'] <= 100 and s['second_tab_ms'] <= 100)
        assert summary['candidate-warm']['passed']
        assert all(summary['candidate-' + state]['passed'] == (prefix == 'completion-scan') for state in ('cold', 'stale', 'unusable'))
    for suffix in ('', '-sanitized'):
        headers = data('completion-headers' + suffix + '/results.json')
        assert headers['cases'] == 2017 and headers['passed']
        rows = data('completion-scan-adversarial' + suffix + '/results.json')
        assert len(rows) == 3 and all(r['equal'] and r['variants'][0] == r['variants'][1] for r in rows)

with tarfile.open(OUT / 'highlight-results.tar.gz') as archive:
    rows = [shlex.split(line) for line in archive.extractfile('highlight-profile/stdout').read().decode().splitlines()]
    assert len(rows) == 400 and not archive.extractfile('highlight-profile/stderr').read()
    summary = read('highlight-summary.json')
    assert summary == json.load(archive.extractfile('highlight-profile/summary.json'))
    for workload, s in summary.items():
        pairs = [{} for _ in range(50)]
        regions = [{} for _ in range(50)]
        for w, i, mode, ms, region in rows:
            if w == workload:
                pairs[int(i)][mode] = float(ms)
                regions[int(i)][mode] = region
        assert pairs == s['pairs'] and all(r['off'] == r['on'] and r['off'] for r in regions)
        for mode in ('off', 'on'):
            close(s['median_ms'][mode], statistics.median(p[mode] for p in pairs))
        close(s['paired_p95_overhead_ms'], sorted(p['on'] - p['off'] for p in pairs)[47])
        functions = {}
        for i in range(50):
            report = archive.extractfile(f'highlight-profile/profile-{workload}-{i}.txt').read().decode()
            for line in report.split('\n\n', 1)[0].splitlines()[2:]:
                fields = line.split()
                if len(fields) == 9 and fields[0].endswith(')'):
                    functions.setdefault(fields[-1], []).append(dict(calls=int(fields[1]), inclusive_ms=float(fields[2]), self_ms=float(fields[5])))
        assert s['functions'] == {name: {key: statistics.median(v[key] for v in values) for key in ('calls', 'inclusive_ms', 'self_ms')} for name, values in functions.items()}
    f = summary['3']['functions']
    total = f['_zsh_highlight_highlighter_main_paint']['inclusive_ms']
    assert f['_zsh_highlight_main_highlighter_highlight_list']['self_ms'] / total > .35
    assert f['_zsh_highlight_main_calculate_fallback']['self_ms'] / total < .20
for component in ('directory', 'history', 'suggestion', 'completion'):
    assert read(component + '-metadata.json')['selected'] is False
print('PASS: five native component experiments, exact parity evidence, measured gates and disabled decisions')
