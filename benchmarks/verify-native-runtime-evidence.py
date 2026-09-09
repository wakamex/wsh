#!/usr/bin/env python3
"""Verify complete C helper contracts, identities and resource thresholds."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'benchmarks/native-render-2026-09-08'
def sha(raw):return hashlib.sha256(raw).hexdigest()
for line in (OUT/'runtime-SHA256SUMS').read_text().splitlines():
    digest,name=line.split('  ',1);assert sha((ROOT/name).read_bytes())==digest,name
meta=json.loads((OUT/'runtime-metadata.json').read_text())
with tarfile.open(OUT/'runtime-inputs.tar.gz') as archive:
    for name,digest in meta['source_inputs'].items():assert sha(archive.extractfile(name).read())==digest,name
with tarfile.open(OUT/'runtime-results.tar.gz') as archive:
    def raw(name):return archive.extractfile(name).read()
    def data(name):return json.loads(raw(name))
    for name,binary in [('runtime-protocol-final','sanitized'),('runtime-protocol-release','c')]:
        rows=data(name+'/decoder.json');assert len(rows)==2237
        assert all(r['passed'] and r['observed']['rust']==r['observed']['c'] for r in rows)
        rows=data(name+'/snapshots.json');assert len(rows)==400
        assert all(r['passed'] and r['observed']['rust']==r['observed']['c'] for r in rows)
        assert data(name+'/metadata.json')['binaries']['c']['sha256']==meta['binaries'][binary]['sha256']
    lifecycle=data('runtime-lifecycle-final/results.json');assert len(lifecycle)==15 and all(r['passed'] for r in lifecycle)
    assert data('runtime-lifecycle-final/metadata.json')['runtime_sha256']==meta['binaries']['sanitized']['sha256']
    for directory,count in [('runtime-git-matrix-1',23),('runtime-git-adversarial-1',10)]:
        rows=data(directory+'/results.json');assert len(rows)==count and all(r['passed'] for r in rows)
    rows=data('runtime-output/results.json');assert len(rows)==4 and all(r['status']==0 and r['response']['type']=='error' for r in rows)
    for name,limit in [('runtime-pipe-cancel',1),('runtime-pipe-timeout',3)]:
        row=data(name+'/result.json');assert row['passed'] and row['descendant_gone'] and row['status']==0
        assert row['active_threads']==2 and row['cancellation_and_shutdown_seconds']<limit
    assert data('runtime-nul-path.json')['expected_difference']
    contracts=data('runtime-contracts-final/results.json');assert len(contracts)==9 and all(r['status']==0 for r in contracts)
    assert b'PASS: hidden isolated internal job' in raw('runtime-pty-final.log')
    for name,variant in [('rust','rust'),('c','c')]:
        content=raw('installations/'+name+'-manifest.json');identity=meta['comparison']['variants'][variant]
        assert sha(content)==identity['manifest_sha256']
        entries={r['path']:r for r in json.loads(content)['files']}
        assert entries['bin/wsh-runtime']['sha256']==meta['binaries'][variant]['sha256']
        assert entries['bin/wsh']['sha256']==meta['native_binary_sha256']
    rows=data('runtime-collection/samples.json');summary=data('runtime-collection/summary.json');assert len(rows)==600
    for key,value in summary.items():
        state,mode=key.split('/');differences=[]
        for pair in range(50):
            selected=[r for r in rows if r['state']==state and r['mode']==mode and r['pair']==pair]
            assert [r['variant'] for r in selected]==(['control','candidate'] if pair%2==0 else ['candidate','control'])
            values={r['variant']:r['collection_ms'] for r in selected};differences.append(values['candidate']-values['control'])
        assert sorted(differences)[47]==value['paired_p95_ms']<=3
    rows=data('runtime-readiness/samples.json');summary=data('runtime-readiness/summary.json');assert len(rows)==200
    for theme,value in summary.items():
        differences=[]
        for pair in range(50):
            selected=[r for r in rows if r['theme']==theme and r['pair']==pair]
            assert [r['variant'] for r in selected]==(['control','native'] if pair%2==0 else ['native','control'])
            values={r['variant']:r['readiness_ms'] for r in selected};differences.append(values['native']-values['control'])
        assert sorted(differences)[47]==value['paired_p95_ms']<=3
    def tsv(name):return list(csv.DictReader(io.StringIO(raw(name).decode()),delimiter='\t'))
    def p90(values):return sorted(values)[math.ceil(len(values)*.9)-1]
    summary=data('runtime-resource-summary.json');rows=tsv('runtime-memory.tsv');assert len(rows)==20
    added=[int(r['added_pss_kib']) for r in rows]
    assert p90(added)==summary['memory']['p90_kib']<=4096 and max(added)==summary['memory']['max_kib']<=5120
    rows=tsv('runtime-trace.tsv');assert len(rows)==60
    for state,value in summary['trace'].items():
        selected=[r for r in rows if r['state']==state];assert len(selected)==20
        assert p90([int(r['ready_overhead_us']) for r in selected])==value['ready_p90_us']<=3000
        assert p90([int(r['refresh_overhead_us']) for r in selected])==value['refresh_p90_us']<=500
print('PASS: complete C helper protocol, lifecycle, native contracts and matched resource gates')
