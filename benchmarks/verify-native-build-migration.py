#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import tarfile
root=Path(__file__).resolve().parent/'native-consolidation-2026-09-10'
identity=json.loads((root/'build-identity.json').read_text())
archive=root/'build-evidence.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==identity['archive_sha256']
with tarfile.open(archive) as t:
    for name,digest in identity['source'].items():
        assert hashlib.sha256(t.extractfile(name).read()).hexdigest()==digest
    rows=json.load(t.extractfile('contracts/results.json'))
    assert len(rows)==9 and all(r['status']==0 for r in rows)
    raw=t.extractfile('manifest.json').read()
    assert hashlib.sha256(raw).hexdigest()==identity['bundle']
    manifest=json.loads(raw)
    assert manifest['schema_version']==2 and 'rust' not in manifest and 'minimum_manager_version' not in manifest
    assert b'PASS: 15 ' in t.extractfile('manifest-tests.log').read()
    assert b'unexpected Rust tool invocation' not in t.extractfile('build.log').read()
print('PASS: native build, inventory, installed contracts and RPM assembly without Rust tools')
