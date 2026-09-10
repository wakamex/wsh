#!/usr/bin/env python3
"""Verify recognized upstream handoff contracts and paired startup gates."""
import hashlib
import json
from pathlib import Path
import tarfile
import subprocess

root = Path(__file__).resolve().parents[1]
evidence = root / 'benchmarks/native-highlighting-handoff-2026-09-10'
identity = json.loads((evidence / 'identity.json').read_text())
assert identity['binary_sha256'] == identity['parser_test_binary_sha256']
for name, digest in identity['current_sources'].items():
    data = (root / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        data = subprocess.check_output(['git', 'show', '1f9c258:' + name], cwd=root)
    assert hashlib.sha256(data).hexdigest() == digest, name
archive = evidence / 'evidence.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
with tarfile.open(archive) as t:
    for name, digest in identity['archive_files'].items():
        assert hashlib.sha256(t.extractfile(name).read()).hexdigest() == digest, name
    def read(name):
        return json.load(t.extractfile(name))
    assert b'PASS: syntax highlighting ownership' in t.extractfile('ownership.log').read()
    contracts = read('contracts-final/results.json')
    assert len(contracts) == 9 and all(r['status'] == 0 for r in contracts)
    rows = read('installed/prefixes/results.json')
    assert len(rows) == 3360 and all(r['equal'] and r['control'] == r['candidate'] for r in rows)
    assert read('installed/prefixes/summary.json')['input_executed'] is False
    assert read('installed/lifetime/result.json')['retained_growth_kib'] <= 8192
    samples = read('startup-final/samples.json')
    summary = read('startup-final/summary.json')
    assert len(samples) == 200
    for theme, result in summary.items():
        rows = [r for r in samples if r['theme'] == theme]
        data = {v: [r['readiness_ms'] for r in rows if r['variant'] == v] for v in ('control', 'native')}
        assert len(data['control']) == len(data['native']) == result['pairs'] == 50
        delta = sorted(data['native'][i] - data['control'][i] for i in range(50))[47]
        assert delta == result['paired_p95_ms'] <= result['gate_ms'] == 3
        assert result['passed']
        assert sorted(data['control'])[24] == result['control_median_ms']
        assert sorted(data['native'])[24] == result['native_median_ms']
    personal = read('personal-config-result.json')
    assert personal['wsh_native_main'] and not personal['regular_zsh_native_main']
    assert personal['quoted_command_regions_equal'] and personal['config_unchanged']
    assert b'PASS: real RPM agreement' in t.extractfile('floor.log').read()
    floor_contracts = read('floor-checks/contracts/results.json')
    assert len(floor_contracts) == 9 and all(r['status'] == 0 for r in floor_contracts)
    floor_prefixes = read('floor-checks/highlighting/prefixes/results.json')
    assert len(floor_prefixes) == 3360 and all(r['equal'] for r in floor_prefixes)
    assert b'75 successful test scripts, 0 failures, 2 skipped' in t.extractfile('floor-build.log').read()
print('PASS: recognized older/current highlighting handoff, preserved customization and paired startup gates')
