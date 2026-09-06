#!/usr/bin/env python3
"""Verify the matched startup-order experiment without rerunning timings."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
out = root / 'benchmarks/profile-order-investigation-2026-09-06'
for line in (out / 'SHA256SUMS').read_text().splitlines():
    expected, name = line.split('  ', 1)
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name

metadata = json.loads((out / 'metadata.json').read_text())
for name, expected in metadata['inputs'].items():
    data = subprocess.check_output(['git', '-C', str(root), 'show',
                                    metadata['source_revision'] + ':' + name])
    assert hashlib.sha256(data).hexdigest() == expected, name

builds = json.loads((out / 'builds.json').read_text())
for key in ['manager_sha256', 'runtime_sha256', 'zsh_sha256']:
    assert len({build[key] for build in builds.values()}) == 1, key
payloads = {}
for name, build in builds.items():
    data = gzip.decompress((out / (name + '-manifest.json.gz')).read_bytes())
    assert hashlib.sha256(data).hexdigest() == build['manifest_sha256']
    manifest = json.loads(data)
    assert manifest['status'] == 'development'
    assert manifest['rust']['source_revision'] == build['revision']
    files = {f['path']: f['sha256'] for f in manifest['files'] if 'sha256' in f}
    assert files['bin/zsh'] == build['zsh_sha256']
    assert files['bin/wsh-runtime'] == build['runtime_sha256']
    payloads[name] = files
for name in ['modules', 'both']:
    changed = {p for p in payloads['baseline'].keys() | payloads[name].keys()
               if payloads['baseline'].get(p) != payloads[name].get(p)}
    assert changed == {'share/wsh/zdotdir/.zshenv'}, (name, changed)

runs = json.loads((out / 'runs.json').read_text())
assert [r['variant'] for r in runs] == ['baseline', 'modules', 'both', 'both', 'modules', 'baseline']
for index, run in enumerate(runs, 1):
    assert run['index'] == index
    prefix = out / f"{index}-{run['variant']}"
    with Path(str(prefix) + '-samples.tsv').open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    assert len(rows) == 200
    pairs = {}
    first, settled = {'normal': [], 'profile': []}, {'normal': [], 'profile': []}
    for row in rows:
        variant = row['variant']
        assert variant in first and row['block'] in ('forward', 'reverse')
        assert 1 <= int(row['repetition']) <= 50
        expected_order = ('normal', 'profile') if row['block'] == 'forward' else ('profile', 'normal')
        assert variant == expected_order[int(row['position']) - 1]
        key = row['block'], row['repetition']
        pair = pairs.setdefault(key, {})
        assert variant not in pair
        start, end = float(row['first_editable_ms']), float(row['settled_ms'])
        assert 0 < start <= end
        pair[variant] = start, end - start
        first[variant].append(start)
        settled[variant].append(end)
    assert len(pairs) == 100 and all(set(p) == {'normal', 'profile'} for p in pairs.values())
    values = {('first-editable', v): first[v] for v in first}
    values.update({('settled', v): settled[v] for v in settled})
    overhead = [p['profile'][0] - p['normal'][0] for p in pairs.values()]
    values['first-editable-overhead', 'paired'] = overhead
    values['refresh-overhead-diagnostic', 'paired'] = [p['profile'][1] - p['normal'][1] for p in pairs.values()]
    with Path(str(prefix) + '-summary.tsv').open() as stream:
        summary = list(csv.DictReader(stream, delimiter='\t'))
    assert len(summary) == len(values)
    for row in summary:
        ordered = sorted(values.pop((row['metric'], row['variant'])))
        assert int(row['samples']) == len(ordered) == 100
        for field, expected in [('median_ms', ordered[49]), ('p90_ms', ordered[89]), ('maximum_ms', ordered[-1])]:
            assert abs(float(row[field]) - expected) < .0000011, (prefix, field)
    p90 = sorted(overhead)[89]
    assert p90 <= 3.0, (prefix, p90)
    expected_gate = f'profile-first-editable-p90-overhead-ms\t<=3.000\t{p90:.3f}\tpass'
    assert Path(str(prefix) + '-gates.tsv').read_text().splitlines()[1] == run['gate'] == expected_gate

print('PASS: matched binaries, historical inputs, 600 profile pairs, six summaries, and unchanged 3 ms gates agree')
