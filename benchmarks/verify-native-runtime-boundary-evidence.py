#!/usr/bin/env python3
"""Check the rejected embedding probe and passing helper cost evidence."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'benchmarks/native-runtime-boundary-2026-09-09'
def sha(raw):return hashlib.sha256(raw).hexdigest()
for line in (OUT/'SHA256SUMS').read_text().splitlines():
    digest,name=line.split('  ',1);assert sha((ROOT/name).read_bytes())==digest,name
meta=json.loads((OUT/'metadata.json').read_text())
with tarfile.open(OUT/'inputs.tar.gz') as a:
    for name,digest in meta['source_inputs'].items():assert sha(a.extractfile(name).read())==digest
    for name,digest in meta['configured_headers'].items():assert sha(a.extractfile('configured-zsh/'+name).read())==digest
with tarfile.open(OUT/'results.tar.gz') as a:
    def raw(name):return a.extractfile(name).read()
    def data(name):return json.loads(raw(name))
    normal=data('ownership-final/results.json');suppressed=data('ownership-suppressed/results.json')
    assert normal['module_cases']==suppressed['module_cases']==100
    assert normal['module_successes']==4 and len(normal['module_errors'])==96
    assert all('could not wait for Git status' in value for value in normal['module_errors'])
    assert suppressed['module_successes']==normal['helper_successes']==suppressed['helper_successes']==100
    assert normal['binaries']==suppressed['binaries']
    for name in ['ownership-final','ownership-suppressed','ownership-sanitized']:
        result=data(name+'/results.json');assert result['module_cases']==result['helper_successes']==100
        assert not raw(name+'/stderr')
        assert len(data(name+'/control.json'))==100
    jobs=data('background-job-final.json');assert jobs[0]['status']==0 and jobs[0]['stdout']=='WSH_JOB:0\n'
    assert jobs[1]['suppressed'] and jobs[1]['timed_out'] and jobs[1]['seconds']>=3
    ipc=data('ipc.json');rows=ipc['samples'];assert len(rows)==1000 and [r['pair'] for r in rows]==list(range(1,1001))
    values=sorted(r['elapsed_ns'] for r in rows)
    assert ipc['summary']['p95_ns']==values[949] and ipc['summary']['median_ns']==(values[499]+values[500])/2
    assert ipc['summary']['empty_p95_ns']==sorted(r['empty_ns'] for r in rows)[949]
    assert ipc['binary_sha256']==normal['binaries']['helper']['sha256']
print('PASS: native child-ownership conflict, rejected signal suppression and measured helper round trips')
