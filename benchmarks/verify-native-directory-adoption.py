#!/usr/bin/env python3
"""Verify repaired directory prototype behavior without claiming full adoption."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import tarfile

out = Path(__file__).resolve().parents[1] / 'benchmarks/native-adoption-2026-09-10/directory'
for line in (out/'SHA256SUMS').read_text().splitlines():
    digest,name=line.split('  ',1)
    assert hashlib.sha256((out/name).read_bytes()).hexdigest()==digest,name
identity=json.loads((out/'identity.json').read_text())
assert identity['selected'] is False
with tarfile.open(out/'inputs.tar.gz') as archive:
    for name,digest in identity['input_sha256'].items():
        assert hashlib.sha256(archive.extractfile(name).read()).hexdigest()==digest,name
with tarfile.open(out/'results.tar.gz') as archive:
    def read(name):
        return json.load(archive.extractfile(name))
    for suffix in ('','-sanitized'):
        rows=read('directory-final-query'+suffix+'/results.json')
        assert len(rows)==720 and all(r['equal'] and r['results'][0]==r['results'][1] for r in rows)
        assert all(v['status']==0 and not v['stderr'] for r in rows for v in r['results'])
        rows=read('directory-final-mutations'+suffix+'/results.json')
        assert len(rows)==10 and all(r['exact_equal']==(r['variants'][0]==r['variants'][1]) for r in rows)
        assert {r['name'] for r in rows if not r['exact_equal']}=={'tab'}
        rows=read('directory-final-persistence'+suffix+'/results.json')
        assert len(rows)==7
        for r in rows:
            if r['test']=='tab-roundtrip':
                assert r['add']['status']==0 and r['query']['status']==(1 if r['owner']=='control' else 0)
            elif r['test']=='real-zsh-flock-timeout':
                assert r['result']['status']==2
            elif r['test']=='lock-release-recovery':
                assert r['result']['status']==0
            elif r['test']=='twenty-mixed-writers':
                assert len(r['results'])==20 and all(v['status']==0 and not v['stderr'] for v in r['results'])
                assert bytes.fromhex(r['database']).endswith(b'|22|1800000000\n')
        rows=read('directory-qualified-lifecycle'+suffix+'/results.json')
        assert len(rows)==3 and all(r['equal'] and r['variants'][0]==r['variants'][1] for r in rows)
        rows=read('directory-qualified-lifecycle'+suffix+'/custom-unload.json')
        assert rows[0]==rows[1] and all(r['status']==0 and not r['stderr'] for r in rows)
        rows=read('directory-final-zle'+suffix+'/results.json')
        assert len(rows)==2 and rows[0]==rows[1] and len(rows[0])==3
    for label in ('directory-lifecycle-before','directory-reload-before'):
        assert any(not r['equal'] for r in read(label+'/results.json'))
    for label in ('directory-qualified-cost','directory-warm-lookup'):
        summary=read(label+'/summary.json')
        for name,row in summary.items():
            pairs=row['pairs']
            assert len(pairs)==50
            for owner in ('control','candidate'):
                assert all(math.isfinite(p[owner]) and p[owner]>0 for p in pairs)
                assert row['median_ms'][owner]==statistics.median(p[owner] for p in pairs)
            delta=sorted(p['candidate']-p['control'] for p in pairs)[47]
            assert row['paired_p95_delta_ms']==delta and delta<=3
            reduction=1-row['median_ms']['candidate']/row['median_ms']['control']
            assert math.isclose(row['median_reduction'],reduction)
            if name.startswith('1000') and 'write' not in name:
                assert reduction>=.20
print('PASS: directory persistence, real flock/writers, lifecycle, editor and measured prototype costs')
