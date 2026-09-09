#!/usr/bin/env python3
"""Check the complete named ownership counts and installed payload accounting."""
import hashlib
import json
from pathlib import Path
import tarfile
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-qualification-2026-09-09'
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
for line in (OUT / 'inventory-SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest
data = json.loads((OUT / 'responsibility-inventory.json').read_text())
with tarfile.open(OUT / 'inventory-inputs.tar.gz') as a:
    for group, record in data.items():
        if group == 'payload':
            continue
        for row in record['files']:
            raw = a.extractfile(row['path']).read()
            assert sha(raw) == row['sha256']
            assert len(raw) == row['bytes'] and len(raw.splitlines()) == row['lines']
        assert sum(r['lines'] for r in record['files']) == record['lines']
        assert sum(r['bytes'] for r in record['files']) == record['bytes']
    raw = a.extractfile('payload-manifest.json').read()
    manifest = json.loads(raw)
    assert sha(raw) == data['payload']['manifest_sha256']
    assert len(manifest['files']) + 1 == data['payload']['files']
    assert sum(f['size'] for f in manifest['files']) + len(raw) == data['payload']['bytes']
    assert manifest['requirements']['dynamic_libraries'] == data['payload']['required_libraries']
print('PASS: native ownership source counts, retained legacy/prototype costs and full payload accounting')
