#!/usr/bin/env python3
"""Recompute installed completion gates and verify retained source identities."""
import hashlib
import json
import math
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
out = root / 'benchmarks/native-adoption-2026-09-10/completion'
for line in (out / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest, name
identity = json.loads((out / 'identity.json').read_text())
with tarfile.open(out / 'inputs.tar.gz') as archive:
    for name, digest in identity['input_sha256'].items():
        assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest, name
with tarfile.open(out / 'results.tar.gz') as archive:
    def read(name):
        return json.load(archive.extractfile(name))
    for label in ('fixed', 'joined'):
        run = 'completion-installed-' + label
        rows = read(run + '/zle/samples.json')
        summary = read(run + '/zle/summary.json')
        assert len(rows) == 450 and len(summary) == 9
        for variant, expected in summary.items():
            samples = [r for r in rows if r['variant'] == variant]
            assert len(samples) == 50 and {r['pair'] for r in samples} == set(range(50))
            for metric in ('startup_ms',) if variant == 'baseline' else ('startup_ms', 'first_tab_ms', 'second_tab_ms'):
                values = [r[metric] for r in samples]
                assert all(math.isfinite(v) and v > 0 for v in values)
                assert expected[metric] == sorted(values)[47]
            if variant == 'baseline':
                continue
            overhead = expected['startup_ms'] - summary['baseline']['startup_ms']
            limit = 20 if variant.endswith('-warm') else 100
            assert math.isclose(overhead, expected['startup_overhead_ms'], abs_tol=1e-8)
            assert expected['startup_limit_ms'] == limit
            passed = overhead <= limit and expected['first_tab_ms'] <= 100 and expected['second_tab_ms'] <= 100
            assert expected['passed'] == passed
            if variant.startswith('candidate-'):
                assert passed == (label == 'joined' or variant.endswith('-warm'))
    for run in ('completion-installed-joined', 'completion-installed-sanitized-joined'):
        results = read(run + '/correctness-results.json')
        assert len(results) == 5 and all(r['status'] == 0 for r in results)
        assert any(r['test'] == 'debug-trap-header-lifetime' for r in results)
        assert len(read(run + '/zle/correctness.json')) == 13
        assert not archive.extractfile(run + '/debug-trap.stderr').read()
    assert b'heap-use-after-free' in archive.extractfile('debug-trap-before/stderr').read()
print('PASS: installed completion source identities, lifetime regression, sample counts and fixed gates')
