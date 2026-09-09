#!/usr/bin/env python3
"""Verify private migration preservation and actual Wakterm caller test evidence."""
import hashlib
import json
from pathlib import Path
import tarfile
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-qualification-2026-09-09'
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
for line in (OUT / 'migration-SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest
meta = json.loads((OUT / 'migration-metadata.json').read_text())
with tarfile.open(OUT / 'migration-inputs.tar.gz') as a:
    for name, digest in meta['source_inputs'].items():
        assert sha(a.extractfile(name).read()) == digest
    caller = a.extractfile('wakterm-session_persistence.rs').read()
    assert b'--wsh-run' in caller and b'--login' in caller
with tarfile.open(OUT / 'migration-results.tar.gz') as a:
    results = json.load(a.extractfile('migration/results.json'))
    assert len(results) == 4 and all(r['passed'] for r in results)
    log = a.extractfile('wakterm-caller-tests-final.log').read()
    assert b'3 passed; 0 failed' in log
print('PASS: private native PATH migration, preserved user files and actual Wakterm restore caller')
