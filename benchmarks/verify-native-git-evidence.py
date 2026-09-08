#!/usr/bin/env python3
"""Verify the opt-in C collector's retained identities, correctness and fixed gates."""
import csv
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-git-2026-09-08'
sha = lambda raw: hashlib.sha256(raw).hexdigest()
for line in (OUT / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest, name
meta = json.loads((OUT / 'metadata.json').read_text())
with tarfile.open(OUT / 'inputs.tar.gz') as archive:
    for name, digest in meta['source_inputs'].items():
        assert sha(archive.extractfile(name).read()) == digest, name
    for name, count in meta['source_lines'].items():
        assert len(archive.extractfile(name).read().splitlines()) == count
    assert sum(meta['source_lines'][n] for n in ['native/git.c', 'native/git.h']) == 607
    assert sum(meta['source_lines'][n] for n in ['crates/wsh-runtime/src/native_git.rs', 'crates/wsh-runtime/build.rs']) == 160
    cargo = archive.extractfile('crates/wsh-runtime/Cargo.toml').read()
    assert b'native-git = []' in cargo and b'default = [' not in cargo
    comparison_test = archive.extractfile('crates/wsh-runtime/src/git_comparison.rs').read()
    assert b'0..10015' in comparison_test and b'parse_git_status(' in comparison_test
    lock = json.load(archive.extractfile('build/zsh-sources/zsh-cad0d67c-native.json'))
    for entry in lock['source_patches'] + lock['test_patches'] + lock['native']['sources']:
        assert sha(archive.extractfile(entry['path']).read()) == entry['sha256']
prior = json.loads((ROOT / 'benchmarks/git-pipe-lifetime-2026-09-08/metadata.json').read_text())
assert meta['native_binary_sha256'] == prior['binary_sha256']
assert meta['binaries']['rust']['size'] - meta['binaries']['c']['size'] == 105600
with tarfile.open(OUT / 'results.tar.gz') as archive:
    def raw(name): return archive.extractfile(name).read()
    def data(name): return json.loads(raw(name))
    def rows(name): return list(csv.DictReader(io.StringIO(raw(name).decode()), delimiter='\t'))
    manifests = {}
    for variant in ['rust', 'c']:
        body = raw('installations/' + variant + '-manifest.json')
        manifest = json.loads(body); manifests[variant] = {e['path']: e for e in manifest['files']}
        assert sha(body) == meta['comparison']['variants'][variant]['manifest_sha256']
        assert manifest['status'] == 'development'
        assert manifests[variant]['bin/wsh-runtime']['sha256'] == meta['binaries'][variant]['sha256']
    assert {k:v for k,v in manifests['rust'].items() if k != 'bin/wsh-runtime'} == {k:v for k,v in manifests['c'].items() if k != 'bin/wsh-runtime'}
    initial = data('matrix-1/results.json')
    assert [r['case'] for r in initial if not r['passed']] == ['non-utf8-packed-tags']
    assert b'case 4:' in raw('parser-1.log') and b'test result: FAILED' in raw('parser-1.log')
    for name in ['matrix-final', 'matrix-sanitized-final']:
        matrix = data(name + '/results.json'); assert len(matrix) == 23 and all(r['passed'] for r in matrix)
        for case in matrix:
            if case['case'] == 'relative-cwd-rejected':
                assert all(s['error_type'] == 'error' for s in case['snapshots'].values())
            else:
                assert case['snapshots']['rust'] == case['snapshots']['native']
                assert case['snapshots']['native']['generation'] == 2**64 - 1
    for name in ['rust-refactor-tests-final.log', 'c-tests-formatted.log', 'sanitized-tests-1.log', 'parser-final.log']:
        assert b'0 failed' in raw(name) and b'test result: FAILED' not in raw(name)
    assert b'1 passed; 0 failed; 0 ignored' in raw('parser-final.log')
    for name in ['adversarial-final', 'adversarial-sanitized']:
        cases = data(name + '/results.json'); assert len(cases) == 10 and all(c['passed'] for c in cases)
        assert len([m for m in cases[-1]['messages'] if m['type'] == 'cancelled']) == 50
        assert cases[-1]['messages'][-1]['snapshot']['generation'] == 51
        assert all(c['elapsed_seconds'] < 3 for c in cases[:-1])
    for name in ['output-c-final', 'output-sanitized']:
        cases = data(name + '/results.json'); assert len(cases) == 4
        assert all(c['status'] == 0 and c['response']['type'] == 'error' for c in cases)
    for name, limit in [('pipe-c-final', 1), ('pipe-sanitized', 1), ('timeout-sanitized', 3)]:
        case = data(name + '/result.json')
        assert case['passed'] and case['status'] == 0 and case['descendant_gone'] and case['active_threads'] == 3
        assert case['cancellation_and_shutdown_seconds'] < limit
    contracts = data('c-contracts/results.json'); assert len(contracts) == 9 and all(c['status'] == 0 for c in contracts)
    assert b'PASS: hidden isolated internal job' in raw('c-runtime-pty.log')
    samples = data('c-collection/samples.json'); summary = data('c-collection/summary.json'); assert len(samples) == 600
    for state in ['clean', 'dirty', 'untracked']:
        for mode in ['process-cold', 'warm']:
            differences = []
            for pair in range(50):
                selected = [r for r in samples if r['state'] == state and r['mode'] == mode and r['pair'] == pair]
                assert [r['variant'] for r in selected] == (['control', 'candidate'] if pair % 2 == 0 else ['candidate', 'control'])
                values = {r['variant']: r['collection_ms'] for r in selected}
                differences.append(values['candidate'] - values['control'])
            observed = sorted(differences)[47]
            assert observed <= 3 and abs(observed - summary[state + '/' + mode]['paired_p95_ms']) < 1e-9
    samples = data('c-readiness/samples.json'); summary = data('c-readiness/summary.json'); assert len(samples) == 200
    for theme in ['existing', 'minimal']:
        differences = []
        for pair in range(50):
            selected = [r for r in samples if r['theme'] == theme and r['pair'] == pair]
            assert [r['variant'] for r in selected] == (['control', 'native'] if pair % 2 == 0 else ['native', 'control'])
            values = {r['variant']: r['readiness_ms'] for r in selected}; differences.append(values['native'] - values['control'])
        observed = sorted(differences)[47]
        assert observed <= 3 and abs(observed - summary[theme]['paired_p95_ms']) < 1e-9
    resource = data('c-summary.json')
    memory = rows('c-memory-cpu0.tsv'); assert len(memory) == 20
    values = []
    for index, row in enumerate(memory, 1):
        assert int(row['iteration']) == index and row['order'] == ('raw-first' if index % 2 else 'wsh-first')
        assert int(row['wsh_combined_pss_kib']) == int(row['wsh_zsh_pss_kib']) + int(row['wsh_runtime_pss_kib'])
        value = int(row['wsh_combined_pss_kib']) - int(row['raw_zsh_pss_kib'])
        assert value == int(row['added_pss_kib']); values.append(value)
    assert sorted(values)[17] == resource['memory_p90_kib'] <= 4096
    assert max(values) == resource['memory_max_kib'] <= 5120
    traces = rows('c-runtime-trace-cpu0.tsv'); assert len(traces) == 60
    ready = []
    for state in ['clean', 'dirty', 'untracked']:
        selected = [r for r in traces if r['state'] == state]; assert len(selected) == 20
        assert {int(r['iteration']) for r in selected} == set(range(1, 21))
        refresh = []
        for row in selected:
            assert row['order'] == ('plain-first' if int(row['iteration']) % 2 else 'traced-first')
            assert int(row['ready_overhead_us']) == int(row['traced_ready_us']) - int(row['plain_ready_us'])
            assert int(row['refresh_overhead_us']) == int(row['traced_refresh_us']) - int(row['plain_refresh_us'])
            ready.append(int(row['ready_overhead_us'])); refresh.append(int(row['refresh_overhead_us']))
        assert sorted(refresh)[17] == resource['trace_refresh_p90_us'][state] <= 500
    assert sorted(ready)[53] == resource['trace_ready_p90_us'] <= 3000
print('PASS: opt-in C Git collector parity, sanitizer evidence, cancellation, matched latency and resource gates')
