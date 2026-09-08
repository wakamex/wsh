#!/usr/bin/env python3
"""Verify retained native-tool evidence without executing timing experiments."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-tools-2026-09-08'
for line in (OUT/'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
build = json.loads((OUT/'build.json').read_text())
with tarfile.open(OUT/'version-inputs.tar.gz') as archive:
    for name, digest in build['inputs'].items():
        assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest, name
identity = hashlib.sha256(json.dumps(build['inputs'], sort_keys=True).encode()).hexdigest()
assert identity == build['build_identity']['WSH_INPUTS_SHA256']
rows = json.loads((OUT/'version-samples.json').read_text())
summary = json.loads((OUT/'version-summary.json').read_text())
assert len(rows) == 50 and [r['pair'] for r in rows] == list(range(50))
assert all(r[key] > 0 for r in rows for key in ('native_ms', 'control_ms'))
p95 = sorted(r['native_ms']-r['control_ms'] for r in rows)[47]
assert abs(p95-summary['paired_p95_ms']) < 1e-9
assert summary['pairs'] == 50 and summary['gate_ms'] == 3 and summary['passed'] and p95 <= 3
assert len(summary['correctness']) == 5
assert '-fsanitize=address,undefined' in summary['sanitizer_command']
print('PASS: native version input identity, boundary checks, sanitizer evidence, sample counts and latency gate')
