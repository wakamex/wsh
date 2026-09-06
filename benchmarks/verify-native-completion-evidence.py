#!/usr/bin/env python3
"""Verify the rejected eager-completion experiment without rerunning timings."""
import gzip
import hashlib
import json
import math
from pathlib import Path
import shlex

root = Path(__file__).resolve().parent.parent
out = root / 'benchmarks/native-completion-2026-09-06'
for line in (out / 'SHA256SUMS').read_text().splitlines():
    expected, name = line.split('  ', 1)
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name

metadata = json.loads((out / 'metadata.json').read_text())
for name, field in [('run.py', 'harness_sha256'), ('plan.md', 'plan_sha256')]:
    assert hashlib.sha256((out / name).read_bytes()).hexdigest() == metadata[field]
original = gzip.decompress((out / 'original-bundle-manifest.json.gz').read_bytes())
assert hashlib.sha256(original).hexdigest() == metadata['bundle_sha256']
manifest = json.loads(original)
assert manifest == json.loads(gzip.decompress((out / 'bundle-manifest.json.gz').read_bytes()))
assert manifest['status'] == 'development'
assert manifest['rust']['source_revision'] == '2239f59bee65b0a083bfb291c15e17548012f828'
files = {f['path']: f['sha256'] for f in manifest['files'] if 'sha256' in f}
assert files['bin/zsh'] == metadata['zsh_sha256']
assert files['bin/wsh-runtime'] == metadata['runtime_sha256']
assert metadata['trace_mode'] == 'off' and metadata['theme'] == ''

def buffers(label):
    transcript = gzip.decompress((out / 'transcripts' / (label + '.gz')).read_bytes())
    assert transcript.index(b'\x1b]133;B\x1b\\') < transcript.index(b'\x1eBUFFER:')
    return [part.split(b'\x1f', 1)[0].decode() for part in transcript.split(b'\x1eBUFFER:')[1:]]

correctness = json.loads((out / 'correctness.json').read_text())
assert [r['variant'] for r in correctness] == ['baseline', 'cold', 'warm']
for row in correctness:
    assert buffers('correctness-' + row['variant']) == [row['branch'], row['jump'], row['path']]
    assert shlex.split(row['path']) == ['cd', 'path with spaces/']
    if row['variant'] == 'baseline':
        assert row['branch'].strip() == 'git switch wsh-native-'
        assert row['jump'].strip() == 'z alpha'
    else:
        assert shlex.split(row['branch']) == ['git', 'switch', 'wsh-native-completion-unique']
        jump = shlex.split(row['jump'])
        assert len(jump) == 2 and jump[0] == 'z' and jump[1].endswith('/fixture/project alpha')

samples = json.loads((out / 'samples.json').read_text())
assert len(samples) == 150
for index in range(50):
    group = samples[index * 3:index * 3 + 3]
    order = ['baseline', 'cold', 'warm'] if index % 2 == 0 else ['warm', 'cold', 'baseline']
    assert [r['variant'] for r in group] == order
    for row in group:
        assert row['round'] == index
        assert buffers(str(index) + '-' + row['variant']) == [row['buffer']]
        expected = 'git switch wsh-native-' if row['variant'] == 'baseline' else 'git switch wsh-native-completion-unique'
        assert row['buffer'].strip() == expected
        assert 0 < row['startup_ms'] < 10000 and 0 < row['tab_ms'] < 10000

summary = json.loads((out / 'summary.json').read_text())
for variant in ['baseline', 'cold', 'warm']:
    rows = [r for r in samples if r['variant'] == variant]
    assert len(rows) == summary['results'][variant]['samples'] == 50
    for metric in ['startup_ms', 'tab_ms']:
        ordered = sorted(r[metric] for r in rows)
        for p in [50, 95]:
            assert summary['results'][variant][metric + '_p' + str(p)] == ordered[math.ceil(len(rows) * p / 100) - 1]
results = summary['results']
baseline = results['baseline']['startup_ms_p95']
gates = {'warm_startup': results['warm']['startup_ms_p95'] - baseline <= 20,
         'cold_startup': results['cold']['startup_ms_p95'] - baseline <= 100,
         'first_tab': max(results[v]['tab_ms_p95'] for v in ['cold', 'warm']) <= 100}
assert summary['gates'] == gates == {'warm_startup': False, 'cold_startup': False, 'first_tab': True}
print('PASS: native completion identities, actual ZLE buffers, 150 samples, summaries, and rejected eager-startup gates agree')
