#!/usr/bin/env python3
"""Recompute the experiment's summaries from retained raw inputs."""
import hashlib
import json
from pathlib import Path
import statistics
import tarfile

ROOT = Path(__file__).resolve().parent
identity = json.loads((ROOT/'identity.json').read_text())
for name, expected in identity['experiment_files'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected, name
summary = json.loads((ROOT/'summary.json').read_text())
with tarfile.open(ROOT/'evidence.tar.gz') as archive:
    def read(name):
        return json.load(archive.extractfile(name))
    for directory in ('protocol', 'protocol-sanitized'):
        rows = read(directory+'/decoder.json')
        assert len(rows) == 2237
        differences = [row for row in rows if row['observed']['control'] != row['observed']['candidate']]
        assert len(differences) == 7 and differences == read(directory+'/differences.json')
        for row in differences:
            frame = bytes.fromhex(row['input_hex'])
            assert b'18446744073709551615' in frame or b':-0' in frame
        rows = read(directory+'/snapshots.json')
        assert len(rows) == 400
        assert all(row['observed']['control'] == row['observed']['candidate'] for row in rows)
    for variant in ('control', 'candidate', 'sanitized'):
        rows = read('lifecycle-'+variant+'/results.json')
        assert len(rows) == 15 and all(row['passed'] for row in rows)
    for name in ('startup', 'git'):
        rows = read(name+'/samples.json')
        retained = read(name+'/summary.json')
        assert retained == summary[name]
        for key, result in retained.items():
            if name == 'startup':
                selected = [r for r in rows if r['theme'] == key]
                variant_key, metric, candidate = 'variant', 'readiness_ms', 'native'
                median_key, gate_key = 'native_median_ms', 'gate_ms'
            else:
                state, mode = key.split('/')
                selected = [r for r in rows if r['state'] == state and r['mode'] == mode]
                variant_key, metric, candidate = 'variant', 'collection_ms', 'candidate'
                median_key, gate_key = 'candidate_median_ms', 'limit_ms'
            values = {v:[r[metric] for r in selected if r[variant_key] == v] for v in ('control',candidate)}
            assert all(len(x) == 50 for x in values.values())
            delta = sorted(c-b for b,c in zip(values['control'], values[candidate]))
            assert result['paired_p95_ms'] == delta[47]
            assert result['control_median_ms'] == sorted(values['control'])[24]
            assert result[median_key] == sorted(values[candidate])[24]
            assert result[gate_key] == 3 and delta[47] <= 3 and result['passed']
    rows = read('memory/samples.json')
    pairs = [{r['owner']:r['pss_kib'] for r in rows if r['pair'] == i} for i in range(20)]
    assert len(rows) == 40 and all(set(p) == {'control','candidate'} for p in pairs)
    for row in rows:
        assert len(row['processes']) == 2
        assert row['pss_kib'] == sum(p['pss_kib'] for p in row['processes'])
    delta = [p['candidate']-p['control'] for p in pairs]
    memory = summary['memory']
    assert memory == read('memory/summary.json')
    assert memory['median_kib'] == {v:statistics.median(p[v] for p in pairs) for v in ('control','candidate')}
    assert memory['max_delta_kib'] == max(delta) <= 4096
    assert memory['p95_delta_kib'] == sorted(delta)[18] and memory['passed']
    ping = read('ping.json')
    values = {v:[r['elapsed_ns'] for r in ping['samples'] if r['variant']==v] for v in ('control','candidate')}
    assert all(len(x) == 1000 for x in values.values())
    delta = sorted(c-b for b,c in zip(values['control'],values['candidate']))
    assert ping['summary'] == summary['ping']
    assert summary['ping']['median_ns'] == {v:statistics.median(x) for v,x in values.items()}
    assert summary['ping']['paired_p95_delta_ns'] == delta[949]
    for variant in ('control','candidate'):
        manifest = read(variant+'-installation/manifest.json')
        helper = next(f for f in manifest['files'] if f['path']=='bin/wsh-runtime')
        assert helper['sha256'] == identity['artifacts'][variant]['helper_sha256']
        assert helper['size'] == summary['executables'][variant]
print('PASS: source/evidence identities, protocol differences, correctness and paired performance summaries')
