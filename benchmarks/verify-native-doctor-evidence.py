#!/usr/bin/env python3
"""Check retained native doctor inputs, behavior, failed runs and fixed gates."""
import gzip
import hashlib
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'benchmarks/native-doctor-2026-09-08'
def read(name):return json.loads((OUT/name).read_text())
def sha(data):return hashlib.sha256(data).hexdigest()
def inputs(directory):
    record=json.loads((directory/'build.json').read_text())
    with tarfile.open(directory/'inputs.tar.gz') as archive:
        for name,digest in record['inputs'].items():assert sha(archive.extractfile(name).read())==digest,name
    assert sha(json.dumps(record['inputs'],sort_keys=True).encode())==record['build_identity']['WSH_INPUTS_SHA256']
    return record
def measurement(directory):
    rows=json.loads((directory/'doctor-samples.json').read_text())
    summary=json.loads((directory/'doctor-summary.json').read_text())
    assert len(rows)==50 and [r['pair'] for r in rows]==list(range(50))
    assert all(row[key]>0 for row in rows for key in ('native_ms','rust_ms'))
    p95=sorted(row['native_ms']-row['rust_ms'] for row in rows)[47]
    assert abs(p95-summary['paired_p95_ms'])<1e-9 and summary['gate_ms']==3
    assert summary['passed']==(p95<=3)
    return summary
for line in (OUT/'SHA256SUMS').read_text().splitlines():
    digest,name=line.split('  ',1);assert sha((ROOT/name).read_bytes())==digest,name
build=inputs(OUT);summary=measurement(OUT)
assert summary['passed'] and summary['native_sha256']==build['binary_sha256']
for number in range(1,5):
    directory=OUT/f'attempt-{number}'
    record=inputs(directory);result=measurement(directory)
    assert result['passed']==(number==4)
    assert record['binary_sha256']==result['native_sha256']
results=read('doctor-results.json')
assert len(results)==14 and all(row['status']==0 for row in results[:9])
assert [row['status'] for row in results[9:]]==[1,1,1,143,0]
assert next(row for row in results if row['fixture']=='hung')['elapsed_seconds']>=9.9
assert len(read('doctor-boundaries.json'))==8
assert read('doctor-boundaries.json')==read('doctor-boundaries-sanitized.json')
manifest=gzip.decompress((OUT/'manifest.json.gz').read_bytes())
assert sha(manifest)==summary['manifest_sha256']
files={entry['path']:entry['sha256'] for entry in json.loads(manifest)['files']}
assert files['bin/wsh']==summary['native_sha256'] and 'bin/wsh-sanitized' not in files
classifier=read('ownership-sanitizer.json')
assert classifier['passed'] and classifier['cases']==40 and classifier['arbitrary_pairs']==10000
with tarfile.open(OUT/'inputs.tar.gz') as archive:
    doctor=archive.extractfile('native/doctor.c').read().decode()
    function='static int\nwsh_doctor_finding'+doctor.split('static int\nwsh_doctor_finding',1)[1].split('\nstatic void\nwsh_doctor_finish',1)[0]
    assert sha(function.encode())==classifier['classifier_sha256']
    assert sha(doctor.encode())==read('sanitized-build.json')['doctor_c_sha256']
assert read('sanitizer-scope.json')['excluded_check']=='function'
assert '75 successful test scripts, 0 failures, 2 skipped' in (OUT/'upstream.log').read_text()
print('PASS: native doctor identities, parity, failure states, cleanup, sanitizer scope, upstream tests and matched latency gate')
