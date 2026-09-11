#!/usr/bin/env python3
"""Verify local Git ownership boundaries and retained startup comparisons."""
import base64
import hashlib
import json
from pathlib import Path
import statistics
import tarfile

root = Path(__file__).resolve().parents[1]
evidence = root/'benchmarks/git-provenance-2026-09-10'
identity = json.loads((evidence/'identity.json').read_text())
for name, digest in identity['sources'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest() == digest, name
archive = evidence/'evidence.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
with tarfile.open(archive) as t:
    for name, digest in identity['files'].items():
        assert hashlib.sha256(t.extractfile(name).read()).hexdigest() == digest, name
    def read(name):
        return json.load(t.extractfile(name))
    for prefix in ('host', 'floor'):
        rows = read(prefix+'/results.json')
        assert len(rows) == 9 and all(r['status'] == 0 for r in rows)
        for matrix in ('plugin-catalog', 'plugin-git-handoff'):
            rows = read(prefix+'/'+matrix+'/results.json')
            assert len(rows) == 80 and all(r['passed'] for r in rows)
            assert len({(r['component'], r['version'], r['variant']) for r in rows}) == 80
        rows = read(prefix+'/plugin-git-boundaries/results.json')
        assert len(rows) == 44 and all(r['passed'] for r in rows)
        assert len({r['case'] for r in rows}) == 44
    actual = read('actual-upstream.json')
    data = base64.b64decode(actual['github_response']['content'])
    assert hashlib.sha256(data).hexdigest() == actual['sha256']
    assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() == actual['github_response']['sha']
    assert actual['revision'] == 'cbf0e24b1863c44606bbdd1edcb1c1b40efbcb55'
    catalog = json.loads((root/'third_party/plugin-catalog/catalog.json').read_text())
    assert actual['sha256'] not in {f['sha256'] for e in catalog['entries'] for f in e['files']}
    rows = read('actual-installed/results.json')
    assert len(rows) == 2 and {r['theme'] for r in rows} == {'existing', 'minimal'}
    assert all(r['owner'] == 'wsh' and all(r[k] for k in ('style','legacy_ignore','helpers_removed','displayed','accepted')) for r in rows)
    for workload in ('startup-single', 'startup-all', 'startup-git'):
        samples = read(workload+'/samples.json')
        summary = read(workload+'/summary.json')
        assert len(samples) == 200 and set(summary) == {'existing', 'minimal'}
        for theme, row in summary.items():
            data = {v: [s['readiness_ms'] for s in samples if s['theme'] == theme and s['variant'] == v] for v in ('control','native')}
            assert len(data['control']) == len(data['native']) == row['pairs'] == 50
            delta = sorted(data['native'][i]-data['control'][i] for i in range(50))[47]
            assert delta == row['paired_p95_ms']
            assert sorted(data['control'])[24] == row['control_median_ms']
            assert sorted(data['native'])[24] == row['native_median_ms']
            if workload == 'startup-git':
                assert row['gate_ms'] is None
            else:
                assert delta <= row['gate_ms'] == 3 and row['passed']
    direct = [line.split() for line in t.extractfile('direct-selected-samples.txt').read().decode().splitlines()]
    summary = read('direct-summary.json')
    assert len(direct) == 100
    for variant in ('catalog','git'):
        values = [float(r[2]) for r in direct if r[1] == variant]
        assert len(values) == summary[variant]['samples'] == 50
        assert statistics.median(values) == summary[variant]['median_ms']
    manifest = read('manifest.json')
    binaries = {r['path']:r['sha256'] for r in manifest['files']}
    assert binaries['bin/wsh'] == identity['binary_sha256']
    assert binaries['bin/wsh-runtime'] == identity['runtime_sha256']
    floor = read('floor-manifest.json')
    assert floor['integration_overlay_revision'] == identity['source_revision']
    assert next(r['sha256'] for r in floor['files'] if r['path']=='bin/wsh') == identity['floor_binary_sha256']
print('PASS: Git provenance boundaries, host/floor catalog and fallback matrices, actual upstream ZLE and matched startup evidence')
