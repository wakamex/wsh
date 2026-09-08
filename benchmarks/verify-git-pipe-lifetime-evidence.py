#!/usr/bin/env python3
"""Verify inherited-pipe failure, cancellation fix and retained resource gates."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/git-pipe-lifetime-2026-09-08'
def sha(raw): return hashlib.sha256(raw).hexdigest()
for line in (OUT / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest, name
meta = json.loads((OUT / 'metadata.json').read_text())
with tarfile.open(OUT / 'inputs.tar.gz') as a:
    for name, digest in meta['source_inputs'].items(): assert sha(a.extractfile(name).read()) == digest
    lock = json.load(a.extractfile('build/zsh-sources/zsh-cad0d67c-native.json'))
    for entry in lock['source_patches'] + lock['test_patches'] + lock['native']['sources']:
        assert sha(a.extractfile(entry['path']).read()) == entry['sha256']
manifest = json.loads(gzip.decompress((OUT / 'manifest.json.gz').read_bytes()))
files = {e['path']: e['sha256'] for e in manifest['files']}
assert files['bin/wsh'] == meta['binary_sha256'] and files['bin/wsh-runtime'] == meta['runtime_sha256']
with tarfile.open(OUT / 'results.tar.gz') as a:
    def raw(name): return a.extractfile(name).read()
    def data(name): return json.loads(raw(name))
    def tsv(name): return list(csv.DictReader(io.StringIO(raw(name).decode()), delimiter='\t'))
    old = data('pipe-control-threads/result.json'); new = data('pipe-candidate-threads/result.json')
    assert old['runtime_sha256'] == meta['baseline_runtime_sha256'] and new['runtime_sha256'] == meta['runtime_sha256']
    assert old['status'] == 1 and not old['passed'] and not old['descendant_gone'] and old['active_threads'] == 4
    assert new['status'] == 0 and new['passed'] and new['descendant_gone'] and new['active_threads'] == 3
    assert new['cancellation_and_shutdown_seconds'] < 1
    timeout = data('pipe-timeout/result.json')
    assert timeout['passed'] and timeout['status'] == 0 and timeout['descendant_gone'] and timeout['cancellation_and_shutdown_seconds'] < 3
    assert len(data('output-final/results.json')) == 4 and all(r['status'] == 0 and r['response']['type'] == 'error' for r in data('output-final/results.json'))
    assert b'75 successful test scripts, 0 failures, 2 skipped' in raw('native-build.log')
    assert b'0 failed' in raw('rust-tests-final.log') and b'test result: FAILED' not in raw('rust-tests-final.log')
    assert len(data('contracts/results.json')) == 9 and all(r['status'] == 0 for r in data('contracts/results.json'))
    assert b'PASS: hidden isolated internal job' in raw('runtime-pty.log')
    rows = data('rust-collection/samples.json'); summary = data('rust-collection/summary.json')
    assert len(rows) == 600
    for state in ['clean', 'dirty', 'untracked']:
        for mode in ['process-cold', 'warm']:
            differences = []
            for pair in range(50):
                selected = [r for r in rows if r['state'] == state and r['mode'] == mode and r['pair'] == pair]
                assert [r['variant'] for r in selected] == (['control', 'candidate'] if pair % 2 == 0 else ['candidate', 'control'])
                values = {r['variant']: r['collection_ms'] for r in selected}
                differences.append(values['candidate'] - values['control'])
            observed = sorted(differences)[47]
            assert observed <= 3 and abs(observed - summary[state + '/' + mode]['paired_p95_ms']) < 1e-9
    rows = data('readiness/samples.json'); summary = data('readiness/summary.json'); assert len(rows) == 200
    for theme in ['existing', 'minimal']:
        differences = []
        for pair in range(50):
            selected = [r for r in rows if r['theme'] == theme and r['pair'] == pair]
            assert [r['variant'] for r in selected] == (['control', 'native'] if pair % 2 == 0 else ['native', 'control'])
            values = {r['variant']: r['readiness_ms'] for r in selected}; differences.append(values['native'] - values['control'])
        observed = sorted(differences)[47]
        assert observed <= 3 and abs(observed - summary[theme]['paired_p95_ms']) < 1e-9
    rows = tsv('memory.tsv'); assert len(rows) == 20
    values = []
    for i, r in enumerate(rows, 1):
        assert int(r['iteration']) == i and r['order'] == ('raw-first' if i % 2 else 'wsh-first')
        assert int(r['wsh_combined_pss_kib']) == int(r['wsh_zsh_pss_kib']) + int(r['wsh_runtime_pss_kib'])
        value = int(r['wsh_combined_pss_kib']) - int(r['raw_zsh_pss_kib']); assert value == int(r['added_pss_kib']); values.append(value)
    assert sorted(values)[17] <= 4096 and max(values) <= 5120
    rows = tsv('runtime-trace.tsv'); assert len(rows) == 60
    ready = []
    for state in ['clean', 'dirty', 'untracked']:
        selected = [r for r in rows if r['state'] == state]; assert len(selected) == 20
        assert len({r['iteration'] for r in selected}) == 20
        refresh = []
        for r in selected:
            assert r['order'] == ('plain-first' if int(r['iteration']) % 2 else 'traced-first')
            assert int(r['ready_overhead_us']) == int(r['traced_ready_us']) - int(r['plain_ready_us'])
            assert int(r['refresh_overhead_us']) == int(r['traced_refresh_us']) - int(r['plain_refresh_us'])
            ready.append(int(r['ready_overhead_us'])); refresh.append(int(r['refresh_overhead_us']))
        assert sorted(refresh)[17] <= 500
    assert sorted(ready)[53] <= 3000
print('PASS: Git pipe lifetime, descendant cleanup, protocol liveness, paired latency and resource gates')
