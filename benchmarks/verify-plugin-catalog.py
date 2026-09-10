#!/usr/bin/env python3
"""Verify every admitted snapshot and the matched shared-recognition startup gate."""
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
evidence = root / 'benchmarks/plugin-catalog-2026-09-10'
identity = json.loads((evidence / 'identity.json').read_text())
for name, digest in identity['sources'].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
catalog = json.loads((root / 'third_party/plugin-catalog/catalog.json').read_text())
assert len(catalog['entries']) == 18
archive = evidence / 'evidence.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
with tarfile.open(archive) as t:
    for name, digest in identity['files'].items():
        assert hashlib.sha256(t.extractfile(name).read()).hexdigest() == digest, name
    def read(name):
        return json.load(t.extractfile(name))
    for path in ('contracts-selected', 'floor-contracts'):
        contracts = read(path + '/results.json')
        assert len(contracts) == 9 and all(r['status'] == 0 for r in contracts)
        rows = read(path + '/plugin-catalog/results.json')
        assert len(rows) == 80 and all(r['passed'] for r in rows)
        assert len({(r['component'], r['version'], r['variant']) for r in rows}) == 80
        for entry in catalog['entries']:
            cases = [r for r in rows if (r['component'], r['version']) == (entry['component'], entry['version'])]
            variants = {'exact', 'modified', 'override'}
            if entry['component'] == 'autosuggestions':
                variants |= {'active', 'disabled'}
                if entry['version'] != 'v0.5.2':
                    variants.add('lifecycle-opt-in')
            if len(entry['files']) == 2:
                variants.add('modified-second')
            assert {r['variant'] for r in cases} == variants
    editor = read('correctness/correctness.json')
    assert len(editor) == 10 and all(r['equal'] and r['variants'][0] == r['variants'][1] for r in editor)
    life = read('lifecycle/lifecycle.json')
    assert all(life[k] for k in ('ctrl_c_prompt', 'fd_cleared', 'child_reaped'))
    bounds = read('bounds/bounds.json')
    assert bounds['discarded'] and bounds['fd_cleared']
    assert bounds['response_bytes'] > bounds['limit_bytes'] == 1048576
    assert len(read('omz-selected/results.json')) == 11
    assert all(r['passed'] for r in read('omz-selected/results.json'))
    provenance = read('provenance.json')
    expected = [f['sha256'] for entry in catalog['entries'] for f in entry['files']]
    assert [r['sha256'] for r in provenance] == expected
    for workload in ('startup-single', 'startup-all'):
        samples = read(workload + '/samples.json')
        summary = read(workload + '/summary.json')
        assert len(samples) == 200 and set(summary) == {'existing', 'minimal'}
        for theme, row in summary.items():
            data = {v: [s['readiness_ms'] for s in samples if s['theme'] == theme and s['variant'] == v] for v in ('control', 'native')}
            assert len(data['control']) == len(data['native']) == row['pairs'] == 50
            delta = sorted(data['native'][i] - data['control'][i] for i in range(50))[47]
            assert delta == row['paired_p95_ms'] <= row['gate_ms'] == 3 and row['passed']
            assert sorted(data['control'])[24] == row['control_median_ms']
            assert sorted(data['native'])[24] == row['native_median_ms']
print('PASS: upstream catalog provenance, 80 host/floor handoffs, lifecycle opt-ins and startup gates')
