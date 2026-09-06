#!/usr/bin/env python3
"""Verify login-recovery regression evidence and the healthy-startup gate."""
import gzip
import hashlib
import json
import math
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parent.parent
out = root / 'benchmarks/login-recovery-2026-09-06'
for line in (out / 'SHA256SUMS').read_text().splitlines():
    expected, name = line.split('  ', 1)
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
metadata = json.loads((out / 'metadata.json').read_text())
assert hashlib.sha256((out / 'startup.py').read_bytes()).hexdigest() == metadata['harness_sha256']
assert hashlib.sha256(metadata['config'].encode()).hexdigest() == metadata['fixture_sha256']
assert metadata['trace_mode'] == 'off' and metadata['source_dirty'] is True
with tarfile.open(out / 'implementation.tar.gz', 'r:gz') as archive:
    assert set(archive.getnames()) == set(metadata['inputs'])
    for member in archive.getmembers():
        assert member.isfile()
        assert hashlib.sha256(archive.extractfile(member).read()).hexdigest() == metadata['inputs'][member.name]
for name, key in [('bundle-manifest.json.gz', 'bundle_sha256'), ('floor-manifest.json.gz', 'floor_manifest_sha256')]:
    data = gzip.decompress((out / name).read_bytes())
    assert hashlib.sha256(data).hexdigest() == metadata[key]
    manifest = json.loads(data)
    assert manifest['status'] == 'development'
    if name == 'bundle-manifest.json.gz':
        files = {f['path']: f['sha256'] for f in manifest['files'] if 'sha256' in f}
        assert files['bin/zsh'] == metadata['zsh_sha256'] and files['bin/wsh-runtime'] == metadata['runtime_sha256']
baseline = json.loads((out / 'baseline-login.json').read_text())
assert baseline == {'argv': ['-wsh'], 'status': 1, 'stderr': 'error: no active bundle state\n'}
assert 'AssertionError' in (out / 'baseline.log').read_text()
correctness = (out / 'correctness.log').read_text()
assert len(correctness.splitlines()) == 13 and all(line.startswith('PASS: ') for line in correctness.splitlines())
for name in ['host-suite.log.gz', 'floor-suite.log.gz']:
    log = gzip.decompress((out / name).read_bytes()).decode()
    for line in correctness.splitlines():
        assert line in log, (name, line)
    assert 'PASS: relocated development bundle' in log
    assert 'test result: FAILED' not in log
floor = gzip.decompress((out / 'floor-suite.log.gz').read_bytes()).decode()
assert 'newest imported symbol GLIBC_2.28' in floor
rows = json.loads((out / 'samples.json').read_text())
assert len(rows) == 100
overhead = []
for index in range(50):
    pair = rows[index*2:index*2+2]
    assert [r['variant'] for r in pair] == (['before', 'after'] if index % 2 == 0 else ['after', 'before'])
    assert all(r['round'] == index and r['same_pid_exec'] and 0 < r['startup_ms'] < 8000 for r in pair)
    values = {r['variant']: r['startup_ms'] for r in pair}
    overhead.append(values['after'] - values['before'])
def quantile(values, p):
    return sorted(values)[math.ceil(len(values)*p/100)-1]
summary = json.loads((out / 'summary.json').read_text())
assert summary['pairs'] == 50
assert summary['paired_overhead_p95_ms'] == quantile(overhead, 95)
assert summary['gate_pass'] == (quantile(overhead, 95) <= 3) == True
for variant in ['before', 'after']:
    for p in [50, 95]:
        assert summary['variants'][variant][str(p)] == quantile([r['startup_ms'] for r in rows if r['variant'] == variant], p)
print('PASS: login recovery source identities, baseline failure, host and floor regressions, 50 startup pairs, and fixed 3 ms gate agree')
