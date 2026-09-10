#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import tarfile
root=Path(__file__).resolve().parent/'native-consolidation-2026-09-10'
identity=json.loads((root/'distribution-build-identity.json').read_text())
archive=root/'distribution-build.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==identity['archive_sha256']
with tarfile.open(archive) as t:
    for name,digest in identity['files'].items():
        assert hashlib.sha256(t.extractfile(name).read()).hexdigest()==digest,name
    rows=json.load(t.extractfile('checks/contracts/results.json'))
    assert len(rows)==9 and all(r['status']==0 for r in rows)
    manifest=json.load(t.extractfile('manifest.json'))
    assert manifest['schema_version']==2 and manifest['requirements']['minimum_glibc']=='2.28'
    login=json.load(t.extractfile('vm/distribution-native-login.json'))
    assert login['pam_tty_login'] and login['job_control']
    assert b'LOGIN_AFTER_REFUSED_REMOVAL' in t.extractfile('vm/distribution-remove-guard.log').read()
    assert b'PASS: real RPM agreement' in t.extractfile('logs/floor-native-qualified.log').read()
print('PASS: native distribution floor contracts, inventory, RPM, PAM login and removal guard')
