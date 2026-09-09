#!/usr/bin/env python3
"""Verify native completion timing, passing controls and retained rejected gates."""
import hashlib
import json
import math
from pathlib import Path
import tarfile
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'benchmarks/native-completion-scan-2026-09-09'
def sha(raw):return hashlib.sha256(raw).hexdigest()
for line in (OUT/'SHA256SUMS').read_text().splitlines():
    digest,name=line.split('  ',1);assert sha((ROOT/name).read_bytes())==digest,name
meta=json.loads((OUT/'metadata.json').read_text())
with tarfile.open(OUT/'inputs.tar.gz') as a:
    for name,digest in meta['source_inputs'].items():assert sha(a.extractfile(name).read())==digest
with tarfile.open(OUT/'results.tar.gz') as a:
    def raw(name):return a.extractfile(name).read()
    def data(name):return json.loads(raw(name))
    assert sha(raw('native-manifest.json'))==meta['bundle_sha256']
    for name in ['dump-correctness','dump-bulk']:
        rows=data(name+'/results.json');assert len(rows)==9 and all(r['passed'] for r in rows)
    assert data('header-parity/results.json')['passed'] is False
    headers=data('header-parity-2/results.json');assert headers['passed'] and headers['cases']==2017
    assert raw('header-parity-2/control.stdout')==raw('header-parity-2/candidate.stdout')
    assert data('module-fallback/result.json')['passed']
    samples=data('spans/samples.json');summary=data('spans/summary.json');assert len(samples)==200
    for row in samples:
        clocks=list(map(Decimal,row['clocks']))
        for key,start,end in [('total',0,1),('audit',2,3),('scan',4,5),('dump',6,7)]:assert float((clocks[end]-clocks[start])*1000)==row['spans_ms'][key]
    for state,values in summary.items():
        differences=[]
        for pair in range(50):
            selected=[r for r in samples if r['state']==state and r['pair']==pair]
            assert [r['mode'] for r in selected]==(['plain','timed'] if pair%2==0 else ['timed','plain'])
            times={r['mode']:r['spans_ms']['total'] for r in selected};differences.append(times['timed']-times['plain'])
        assert sorted(differences)[47]==values['instrumentation_paired_p95_ms']<=3
    for directory in ['zle-final','zle-bulk']:
        checks=data(directory+'/correctness.json');assert len(checks)==10 and all(r['passed'] for r in checks)
        rows=data(directory+'/samples.json');summary=data(directory+'/summary.json');assert len(rows)==300
        for variant,values in summary.items():
            selected=[r for r in rows if r['variant']==variant];assert len(selected)==50
            for key in ['startup_ms']+([] if variant=='baseline' else ['first_tab_ms','second_tab_ms']):assert sorted(r[key] for r in selected)[47]==values[key]
            if variant!='baseline':
                overhead=values['startup_ms']-summary['baseline']['startup_ms'];assert overhead==values['startup_overhead_ms']
                passed=overhead<=values['startup_limit_ms'] and values['first_tab_ms']<=100 and values['second_tab_ms']<=100
                assert passed==values['passed']
        assert summary['seed']['passed'] and summary['eager-warm']['passed']
        assert not summary['seed-stale']['passed'] and not summary['seed-unusable']['passed'] and not summary['eager-cold']['passed']
        transcripts=[m for m in a.getmembers() if m.name.startswith(directory+'/transcripts/') and m.name.endswith('.gz')];assert len(transcripts)==310
    assert b'25552' in raw('read-syscalls.txt') and b'1327' in raw('read-syscalls-bulk.txt')
print('PASS: native compinit attribution, readonly seed correctness and retained fallback gate failures')
