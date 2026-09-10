#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import tarfile
root=Path(__file__).resolve().parents[1]
evidence=root/'benchmarks/native-consolidation-2026-09-10'
identity=json.loads((evidence/'retirement-identity.json').read_text())
archive=evidence/'retirement-evidence.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==identity['archive_sha256']
with tarfile.open(archive) as t:
    for name,digest in identity['files'].items():assert hashlib.sha256(t.extractfile(name).read()).hexdigest()==digest
    a=t.extractfile('repro-fixed/a/manifest.json').read();b=t.extractfile('repro-fixed/b/manifest.json').read()
    assert a==b
    sums=t.extractfile('repro-fixed/SHA256SUMS').read().decode().splitlines()
    assert len(sums)==4 and sums[0].split()[0]==sums[2].split()[0]==hashlib.sha256(a).hexdigest()
    assert sums[1].split()[0]==sums[3].split()[0]
    assert b'PASS: independent native installations and RPMs are byte-identical' in t.extractfile('repro-fixed.log').read()
    assert b'PASS: real upgrade, failure, interruption, downgrade' in t.extractfile('vm/distribution-transactions.log').read()
    assert b'REPRODUCED_LOGIN_OK' in t.extractfile('vm/distribution-reproduced-install.log').read()
for path in ('Cargo.toml','Cargo.lock','rust-toolchain.toml','build/rust-toolchain.lock','crates'):
    assert not (root/path).exists(),path
print('PASS: native two-build reproduction, RPM transactions and obsolete Rust source retirement')
