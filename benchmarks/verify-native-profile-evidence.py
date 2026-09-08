#!/usr/bin/env python3
"""Verify native profile source snapshots, correctness results and paired gates."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-profile-2026-09-08'
def sha(data): return hashlib.sha256(data).hexdigest()
for line in (OUT / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest, name
meta = json.loads((OUT / 'metadata.json').read_text())
with tarfile.open(OUT / 'inputs.tar.gz') as a:
    for name, digest in meta['source_inputs'].items():
        assert sha(a.extractfile(name).read()) == digest, name
    raw = a.extractfile('build/zsh-sources/zsh-cad0d67c-native.json').read()
    assert sha(raw) == meta['native_lock_sha256']
    lock = json.loads(raw)
    for entry in lock['source_patches'] + lock['test_patches'] + lock['native']['sources']:
        assert sha(a.extractfile(entry['path']).read()) == entry['sha256']
manifest = json.loads(gzip.decompress((OUT / 'manifest.json.gz').read_bytes()))
files = {f['path']: f['sha256'] for f in manifest['files']}
assert files['bin/wsh'] == meta['binary_sha256']
assert files['bin/wsh-runtime'] == meta['runtime_sha256']
with tarfile.open(OUT / 'results.tar.gz') as a:
    def raw(name): return a.extractfile(name).read()
    def data(name): return json.loads(raw(name))
    def tsv(name): return list(csv.DictReader(io.StringIO(raw(name).decode()), delimiter='\t'))
    for name in ['final-reader', 'sanitized-reader-final']:
        rows = data(name + '/report-cases.json')
        assert len(rows) == 45 and all((r['status'] == 0) == r['accepted'] for r in rows)
    for name in ['final-storage', 'sanitized-storage']:
        rows = data(name + '/storage-results.json')
        assert len(rows) == 9 and all(r['passed'] and r['status'] == r['expected'] for r in rows)
    for name in ['commit-profile', 'sanitized-native']:
        rows = data(name + '/profile-results.json')
        assert len(rows) == 10 and [r['status'] for r in rows] == [23, 7, 9, 11, 13, 2, 2, 2, 2, 17]
    assert len(data('final-startup/startup-results.json')) == 18
    assert len(data('final-contracts/results.json')) == 9
    assert all(r['status'] == 0 for r in data('final-contracts/results.json'))
    assert b'75 successful test scripts, 0 failures, 2 skipped' in raw('build-4.log')
    assert b'PASS: 10000 deterministic' in raw('commit-check-3.log')
    assert b'PASS: readiness waits' in raw('commit-check-1.log')
    assert raw('legacy-c-final-report.txt').split(b'\nStartup\n', 1)[1] == raw('legacy-rust-report.txt').split(b'\nStartup\n', 1)[1]
    for mode in ['existing', 'minimal', 'functions']:
        rows = tsv(mode + '-samples.tsv')
        assert len(rows) == 200
        pairs = {}
        for r in rows:
            key = (r['block'], r['repetition'])
            assert r['variant'] not in pairs.setdefault(key, {})
            pairs[key][r['variant']] = float(r['first_editable_ms'])
        assert len(pairs) == 100 and all(set(v) == {'normal', 'profile'} for v in pairs.values())
        differences = sorted(v['profile'] - v['normal'] for v in pairs.values())
        summary = next(r for r in tsv(mode + '-summary.tsv') if r['metric'] == 'first-editable-overhead')
        assert int(summary['samples']) == 100 and abs(float(summary['p90_ms']) - differences[89]) < 1e-5
        if mode != 'functions': assert differences[89] <= 3
    rows = tsv('runtime-trace.tsv')
    assert len(rows) == 60
    ready = []
    for state in ['clean', 'dirty', 'untracked']:
        selected = [r for r in rows if r['state'] == state]
        assert len(selected) == 20 and len({r['iteration'] for r in selected}) == 20
        refresh = []
        for r in selected:
            assert int(r['ready_overhead_us']) == int(r['traced_ready_us']) - int(r['plain_ready_us'])
            assert int(r['refresh_overhead_us']) == int(r['traced_refresh_us']) - int(r['plain_refresh_us'])
            ready.append(int(r['ready_overhead_us'])); refresh.append(int(r['refresh_overhead_us']))
        assert sorted(refresh)[17] <= 500
    assert sorted(ready)[53] <= 3000
    rows = data('unprofiled/samples.json'); summary = data('unprofiled/summary.json')
    assert len(rows) == 200
    for theme in ['existing', 'minimal']:
        selected = [r for r in rows if r['theme'] == theme]
        differences = []
        for pair in range(50):
            pair_rows = [r for r in selected if r['pair'] == pair]
            assert [r['variant'] for r in pair_rows] == (['control', 'native'] if pair % 2 == 0 else ['native', 'control'])
            values = {r['variant']: r['readiness_ms'] for r in pair_rows}
            differences.append(values['native'] - values['control'])
        p95 = sorted(differences)[47]
        assert p95 <= 3 and abs(summary[theme]['paired_p95_ms'] - p95) < 1e-9
print('PASS: native profile identities, saved-report parity, correctness, sanitizers and matched overhead gates')
