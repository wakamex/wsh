#!/usr/bin/env python3
"""Verify the locked native build, startup contracts and matched timing evidence."""
import gzip
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-build-2026-09-08'
def sha(data): return hashlib.sha256(data).hexdigest()
def read(name): return json.loads((OUT / name).read_text())

for line in (OUT / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest, name
build = read('build.json')
with tarfile.open(OUT / 'inputs.tar.gz') as archive:
    for name, digest in build['source_inputs'].items():
        assert sha(archive.extractfile(name).read()) == digest, name
    lock_bytes = archive.extractfile('build/zsh-sources/zsh-cad0d67c-native.json').read()
    assert sha(lock_bytes) == build['zsh_lock_sha256']
    lock = json.loads(lock_bytes)
    for entry in lock['source_patches'] + lock['test_patches'] + lock['native']['sources']:
        assert sha(archive.extractfile(entry['path']).read()) == entry['sha256']
manifest_bytes = gzip.decompress((OUT / 'manifest.json.gz').read_bytes())
manifest = json.loads(manifest_bytes)
files = {entry['path']: entry for entry in manifest['files']}
assert files['bin/wsh']['sha256'] == build['binary_sha256']
assert not any(name.startswith('zdotdir/') for name in files)
for name, digest in build['matched_resources'].items():
    assert files[name]['sha256'] == digest, name
with tarfile.open(OUT / 'results.tar.gz') as archive:
    def result(name): return json.load(archive.extractfile('final/' + name))
    for prefix in ('', 'sanitized/'):
        assert len(result(prefix + 'startup-results.json')) == 18
        recovery = result(prefix + 'recovery/recovery-results.json')
        assert len(recovery) == 5 and all(row['status'] == 23 for row in recovery)
        assert b'zsh-newuser-install' not in archive.extractfile('final/' + prefix + 'recovery/empty-home.bin').read()
    contracts = result('contracts/results.json')
    assert len(contracts) == 9 and all(row['status'] == 0 for row in contracts)
    assert len(result('lock-guards.json')) == 2
    assert all(row['status'] != 0 for row in result('lock-guards.json'))
    assert b'75 successful test scripts, 0 failures, 2 skipped' in archive.extractfile('wsh-native-locked-clean-home.log').read()
    assert b'zsh-newuser-install' in archive.extractfile('wsh-native-empty-home.bin').read()
rows = read('samples.json')
summary = read('summary.json')
meta = read('metadata.json')
assert len(rows) == 200 and meta['trace_mode'] == 'off' and meta['cpu'] == 0
assert meta['native_sha256'] == build['binary_sha256']
assert meta['control_sha256'] == build['control_binary_sha256']
assert meta['manifest_sha256'] == sha(manifest_bytes)
for theme in ('existing', 'minimal'):
    selected = [row for row in rows if row['theme'] == theme]
    values = {v: [row['readiness_ms'] for row in selected if row['variant'] == v] for v in ('control', 'native')}
    for pair in range(50):
        assert [row['variant'] for row in selected if row['pair'] == pair] == (['control', 'native'] if pair % 2 == 0 else ['native', 'control'])
    differences = sorted(values['native'][i] - values['control'][i] for i in range(50))
    assert summary[theme]['pairs'] == 50 and summary[theme]['gate_ms'] == 3
    assert summary[theme]['passed'] and differences[47] <= 3
    assert abs(summary[theme]['paired_p95_ms'] - differences[47]) < 1e-9
    for variant in ('control', 'native'):
        assert abs(summary[theme][variant + '_median_ms'] - sorted(values[variant])[24]) < 1e-9
print('PASS: locked native build, startup/state/recovery contracts, sanitizer results and matched readiness gates')
