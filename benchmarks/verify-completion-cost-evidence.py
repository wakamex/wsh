#!/usr/bin/env python3
"""Verify component clocks, matched controls, and the unchanged failed gate."""
import ast
from decimal import Decimal
import gzip
import hashlib
import json
import math
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parent.parent
out = root / 'benchmarks/completion-costs-2026-09-06'
previous = root / 'benchmarks/deferred-completion-2026-09-06'
def read(name):
    return json.loads((out / name).read_text())
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def q(values, p):
    return sorted(values)[math.ceil(len(values) * p / 100) - 1]
def close(a, b):
    assert abs(a - b) < 1e-8, (a, b)

for line in (out / 'SHA256SUMS').read_text().splitlines():
    expected, name = line.split('  ', 1)
    assert sha(root / name) == expected, name
metadata = read('metadata.json')
prior = json.loads((previous / 'metadata.json').read_text())
for key in ('manager_source', 'manager_sha256', 'bundle_sha256', 'zsh_sha256', 'runtime_sha256'):
    assert metadata[key] == prior[key], key
for name, key in [('run.py', 'harness_sha256'), ('plan.md', 'plan_sha256'), ('instrumented.zsh', 'prototype_sha256')]:
    assert sha(out / name) == metadata[key]
assert sha(previous / 'run.py') == metadata['reused_harness_sha256']
assert sha(previous / 'deferred.zsh') == metadata['control_prototype_sha256']
prototype = (out / 'instrumented.zsh').read_text()
assert ''.join(line for line in prototype.splitlines(keepends=True) if '_COST_TIMES' not in line) == (previous / 'deferred.zsh').read_text()
assert sum('_COST_TIMES' in line for line in prototype.splitlines()) == 7
def literal(path, name):
    return next(ast.literal_eval(n.value) for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))
config = literal(previous / 'run.py', 'CONFIG') + literal(out / 'run.py', 'EXPORT')
assert hashlib.sha256(config.encode()).hexdigest() == metadata['config_sha256']
manifest_bytes = gzip.decompress((out / 'bundle-manifest.json.gz').read_bytes())
assert hashlib.sha256(manifest_bytes).hexdigest() == metadata['bundle_sha256']
manifest = json.loads(manifest_bytes)
assert manifest['status'] == 'development'
files = {f['path']: f['sha256'] for f in manifest['files'] if 'sha256' in f}
assert files['bin/zsh'] == metadata['zsh_sha256'] and files['bin/wsh-runtime'] == metadata['runtime_sha256']
variance_metadata = read('variance-metadata.json')
assert sha(out / 'variance.py') == variance_metadata['variance_harness_sha256']
assert sha(out / 'variance-plan.md') == variance_metadata['variance_plan_sha256']
assert variance_metadata['control_prototype_sha256'] == metadata['control_prototype_sha256']

with tarfile.open(out / 'transcripts.tar.gz', 'r:gz') as archive:
    assert len(archive.getnames()) == len(set(archive.getnames())) == 413
    transcripts = {}
    for member in archive.getmembers():
        assert member.isfile() and '/' not in member.name and member.name.endswith('.gz')
        transcripts[member.name[:-3]] = gzip.decompress(archive.extractfile(member).read())
def markers(label, marker):
    return [p.split(b'\x1f', 1)[0].decode() for p in transcripts[label].split(marker)[1:]]

correctness = read('correctness.json')
assert [r['variant'] for r in correctness] == ['baseline', 'eager-cold', 'eager-warm', 'deferred-cold', 'deferred-warm', 'existing', 'custom-tab', 'vi', 'z-first']
prior_correctness = json.loads((previous / 'correctness.json').read_text())
for row, control in zip(correctness, prior_correctness):
    label = 'correctness-' + row['variant']
    captures = markers(label, b'\x1eBUFFER:')
    states = [s.split('|') for s in markers(label, b'\x1eSTATE:')]
    assert states[0] == row['before'] and row['after'] in states
    # Buffer semantics must agree with the previously verified fixture, allowing its scratch-root change.
    for key in ('branch', 'jump', 'path', 'second', 'first_jump', 'multiword', 'custom', 'accepted', 'history'):
        assert (key in row) == (key in control)
        if key in row:
            normalized = row[key].replace('/var/tmp/wsh-completion-costs-2026-09-06/', '/var/tmp/wsh-deferred-completion-2026-09-06/')
            assert normalized == control[key], (row['variant'], key)
            assert row[key] in captures
    assert row['after'][2:] == control['after'][2:]
    if 'suggestion' in row:
        assert row['suggestion'][0] == 'SUGGEST_COMPLETE' and row['suggestion'] in states
        assert int(row['highlighted'][1]) > 0 and row['highlighted'] in states

stages = ['autoload', 'compinit', 'directory_jump', 'tab_delegate', 'autosuggestion_rebind', 'native_completion']
def check_row(row, label):
    transcript = transcripts[label]
    assert transcript.index(b'\x1b]133;B\x1b\\') < transcript.index(b'\x1eBUFFER:')
    assert markers(label, b'\x1eBUFFER:') == [row['buffer'], row['buffer']]
    assert row['buffer'] == 'git switch wsh-native-completion-unique '
    exported = markers(label, b'\x1eCOST:')
    assert exported == ['1|' + ','.join(row['clocks'])]
    assert transcript.rindex(b'\x1eBUFFER:') < transcript.index(b'\x1eCOST:')
    assert all(0 < row[key] < 10000 for key in ('startup_ms', 'first_tab_ms', 'second_tab_ms'))
    if '-timed-' in row['variant']:
        assert len(row['clocks']) == 7
        times = [Decimal(value) for value in row['clocks']]
        spans = [float((b - a) * 1000) for a, b in zip(times, times[1:])]
        assert all(value >= 0 for value in spans)
        assert dict(zip(stages, spans)) == row['spans_ms']
        total = float((times[-1] - times[0]) * 1000)
        assert 0 < total <= row['first_tab_ms']
        close(total, sum(spans))
        assert total == row['internal_ms']
        close(row['outer_ms'], row['first_tab_ms'] - total)
    else:
        assert row['clocks'] == [] and 'spans_ms' not in row

checks = read('clock-checks.json')
assert len(checks) == 4
for row in checks:
    check_row(row, 'clock-check-' + row['variant'])
samples, variance = read('samples.json'), read('variance-samples.json')
assert len(samples) == len(variance) == 200
for index in range(50):
    caches = ['cold', 'warm'] if index % 2 == 0 else ['warm', 'cold']
    modes = ['control', 'timed'] if index % 2 == 0 else ['timed', 'control']
    labels = ['a', 'b'] if index % 2 == 0 else ['b', 'a']
    group = samples[index * 4:index * 4 + 4]
    sham = variance[index * 4:index * 4 + 4]
    assert [(r['cache'], r['mode']) for r in group] == [(c, m) for c in caches for m in modes]
    assert [(r['cache'], r['label']) for r in sham] == [(c, label) for c in caches for label in labels]
    for row in group:
        assert row['round'] == index
        check_row(row, str(index) + '-' + row['variant'])
    for row in sham:
        assert row['round'] == index and '-control-' in row['variant']
        check_row(row, 'variance-' + str(index) + '-' + row['cache'] + '-' + row['label'])
summary, variance_summary = read('summary.json'), read('variance-summary.json')
for cache in ('cold', 'warm'):
    rows = [r for r in samples if r['cache'] == cache]
    pairs = [{r['mode']: r for r in rows if r['round'] == i} for i in range(50)]
    delta = [p['timed']['first_tab_ms'] - p['control']['first_tab_ms'] for p in pairs]
    item = summary[cache]
    assert item['pairs'] == 50
    close(item['paired_overhead_median_ms'], q(delta, 50))
    close(item['paired_overhead_p95_ms'], q(delta, 95))
    assert item['instrumentation_gate'] == (q(delta, 95) <= 3) == False
    for mode in ('control', 'timed'):
        selected = [r for r in rows if r['mode'] == mode]
        for metric in ('startup_ms', 'first_tab_ms', 'second_tab_ms'):
            for p in (50, 95):
                close(item['variants'][mode][metric][str(p)], q([r[metric] for r in selected], p))
    selected = [r for r in rows if r['mode'] == 'timed']
    for stage in stages + ['internal_ms', 'outer_ms']:
        values = [r['spans_ms'][stage] if stage in stages else r[stage] for r in selected]
        for p in (50, 95):
            close(item['stages'][stage][str(p)], q(values, p))
    rows = [r for r in variance if r['cache'] == cache]
    pairs = [{r['label']: r for r in rows if r['round'] == i} for i in range(50)]
    delta = [p['b']['first_tab_ms'] - p['a']['first_tab_ms'] for p in pairs]
    item = variance_summary[cache]
    assert item['pairs'] == 50
    close(item['paired_difference_median_ms'], q(delta, 50))
    close(item['paired_difference_p95_ms'], q(delta, 95))
    assert item['exceeds_3_ms_without_clocks'] == (q(delta, 95) > 3) == True
assert read('host.json')['ended'] < read('variance-host.json')['started']
print('PASS: component identities, correctness, buffered clocks, 400 shells, 800 Tab observations, and unchanged failed overhead gates agree')
