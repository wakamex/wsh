#!/usr/bin/env python3
"""Check the retained first-Tab experiment without rerunning measurements."""
import ast
import gzip
import hashlib
import json
import math
from pathlib import Path
import shlex
import tarfile

root = Path(__file__).resolve().parent.parent
out = root / 'benchmarks/deferred-completion-2026-09-06'
for line in (out / 'SHA256SUMS').read_text().splitlines():
    expected, name = line.split('  ', 1)
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name

metadata = json.loads((out / 'metadata.json').read_text())
previous = json.loads((root / 'benchmarks/native-completion-2026-09-06/metadata.json').read_text())
for key in ('manager_source', 'manager_sha256', 'bundle_sha256', 'zsh_sha256', 'runtime_sha256'):
    assert metadata[key] == previous[key], key
for name, field in [('run.py', 'harness_sha256'), ('plan.md', 'plan_sha256'), ('deferred.zsh', 'prototype_sha256')]:
    assert hashlib.sha256((out / name).read_bytes()).hexdigest() == metadata[field], name
config = next(ast.literal_eval(n.value) for n in ast.parse((out / 'run.py').read_text()).body
              if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CONFIG' for t in n.targets))
assert hashlib.sha256(config.encode()).hexdigest() == metadata['config_sha256']
original = gzip.decompress((out / 'bundle-manifest.json.gz').read_bytes())
assert hashlib.sha256(original).hexdigest() == metadata['bundle_sha256']
manifest = json.loads(original)
assert manifest['status'] == 'development'
files = {f['path']: f['sha256'] for f in manifest['files'] if 'sha256' in f}
assert files['bin/zsh'] == metadata['zsh_sha256']
assert files['bin/wsh-runtime'] == metadata['runtime_sha256']
assert metadata['trace_mode'] == 'off' and metadata['theme'] == ''

for name in ('observer-investigation', 'multiword-investigation'):
    attempt = out / name
    identities = json.loads((attempt / 'metadata.json').read_text())
    assert hashlib.sha256((attempt / 'run.py').read_bytes()).hexdigest() == identities['harness_sha256']
    assert 'AssertionError' in (attempt / 'failure.log').read_text()
    assert not (attempt / 'samples.json').exists()

with tarfile.open(out / 'transcripts.tar.gz', 'r:gz') as archive:
    names = archive.getnames()
    assert len(names) == len(set(names)) == 259
    transcripts = {}
    for member in archive.getmembers():
        assert member.isfile() and '/' not in member.name and member.name.endswith('.gz')
        transcripts[member.name[:-3]] = gzip.decompress(archive.extractfile(member).read())

def buffers(label):
    transcript = transcripts[label]
    assert transcript.index(b'\x1b]133;B\x1b\\') < transcript.index(b'\x1eBUFFER:')
    return [p.split(b'\x1f', 1)[0].decode() for p in transcript.split(b'\x1eBUFFER:')[1:]]

variants = ['baseline', 'eager-cold', 'eager-warm', 'deferred-cold', 'deferred-warm']
correctness = json.loads((out / 'correctness.json').read_text())
assert [r['variant'] for r in correctness] == variants + ['existing', 'custom-tab', 'vi', 'z-first']
for row in correctness:
    variant = row['variant']
    transcript = transcripts['correctness-' + variant]
    states = [p.split(b'\x1f', 1)[0].decode().split('|') for p in transcript.split(b'\x1eSTATE:')[1:]]
    assert states[0] == row['before'] and row['after'] in states
    if variant == 'custom-tab':
        assert buffers('correctness-' + variant) == [row['custom']] == ['xCUSTOMTAB']
        assert row['after'][2:4] == ['0', '0']
        continue
    captured = [row[k] for k in ('branch', 'jump', 'path', 'second')]
    if variant == 'z-first':
        assert shlex.split(row['first_jump']) == shlex.split(row['jump'])
        captured.insert(0, row['first_jump'])
    if 'multiword' in row:
        assert shlex.split(row['multiword']) == ['z', 'project alpha']
        captured.append(row['multiword'])
    if variant != 'vi':
        assert row['custom'] == 'ACUSTOM'
        assert row['accepted'] == row['history'] == 'print -r -- DEFER_AUTOSUGGEST_COMPLETE'
        assert row['suggestion'][0] == 'SUGGEST_COMPLETE' and row['suggestion'] in states
        assert int(row['highlighted'][1]) > 0 and row['highlighted'] in states
        captured += [row['custom'], row['accepted'], row['history'], 'nonexistent_deferred_command']
    assert buffers('correctness-' + variant) == captured
    assert row['second'] == row['branch']
    assert shlex.split(row['path']) == ['cd', 'path with spaces/']
    if variant == 'baseline':
        assert row['branch'].strip() == 'git switch wsh-native-' and row['jump'] == 'z alpha'
    else:
        assert shlex.split(row['branch']) == ['git', 'switch', 'wsh-native-completion-unique']
        jump = shlex.split(row['jump'])
        assert jump[0] == 'z' and jump[1].endswith('/fixture/project alpha') and len(jump) == 2
    assert row['after'][4:6] == ['wsh', 'wsh']
    deferred = variant.startswith('deferred-') or variant in ('vi', 'z-first')
    assert row['after'][3] == ('1' if deferred else '0')
    if variant == 'existing':
        assert row['before'][2:] == row['after'][2:]

samples = json.loads((out / 'samples.json').read_text())
assert len(samples) == 250
for index in range(50):
    group = samples[index * 5:index * 5 + 5]
    assert [r['variant'] for r in group] == (variants if index % 2 == 0 else variants[::-1])
    for row in group:
        assert row['round'] == index
        assert buffers(str(index) + '-' + row['variant']) == [row['buffer'], row['buffer']]
        expected = 'git switch wsh-native-' if row['variant'] == 'baseline' else 'git switch wsh-native-completion-unique'
        assert row['buffer'].strip() == expected
        assert all(0 < row[m] < 10000 for m in ('startup_ms', 'tab_ms', 'second_tab_ms'))
summary = json.loads((out / 'summary.json').read_text())
for variant in variants:
    rows = [r for r in samples if r['variant'] == variant]
    assert len(rows) == summary['results'][variant]['samples'] == 50
    for metric in ('startup_ms', 'tab_ms', 'second_tab_ms'):
        ordered = sorted(r[metric] for r in rows)
        for p in (50, 95):
            assert summary['results'][variant][metric + '_p' + str(p)] == ordered[math.ceil(len(rows) * p / 100) - 1]
results = summary['results']
baseline = results['baseline']['startup_ms_p95']
gates = {}
for variant in variants[1:]:
    budget = 100 if variant == 'eager-cold' else 20
    gates[variant] = {'startup': results[variant]['startup_ms_p95'] - baseline <= budget,
                      'first_tab': results[variant]['tab_ms_p95'] <= 100,
                      'second_tab': results[variant]['second_tab_ms_p95'] <= 100}
assert summary['gates'] == gates
for variant in ('deferred-cold', 'deferred-warm'):
    assert gates[variant] == {'startup': True, 'first_tab': False, 'second_tab': True}
print('PASS: deferred completion identities, nine correctness cases, 250 shells, 500 Tab buffers, quantiles, and failed first-Tab gates agree')
