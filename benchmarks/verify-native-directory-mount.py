#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import tarfile
root = Path(__file__).resolve().parent/'native-directory-final-2026-09-10'
identity = json.loads((root/'mount-identity.json').read_text())
archive = root/'mount.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
with tarfile.open(archive) as t:
    for path, digest in identity['source'].items():
        assert hashlib.sha256(t.extractfile(path).read()).hexdigest() == digest
    for mode, count in [('normal', 4), ('sanitized', 2)]:
        rows = json.load(t.extractfile(mode+'/results.json'))
        assert len(rows) == count
        for row in rows:
            assert row['inode_preserved'] and not row['stderr']
            assert row['status'] == (1 if row['readonly'] else 0)
            assert (row['database'] == row['before']) == row['readonly']
            if not row['readonly']:
                assert row['mode'] == 0o600
                assert bytes.fromhex(row['database']).endswith(b'|3|1800000000\n')
                if mode == 'normal' and row['owner'] == 'candidate':
                    assert row['mixed_writers'] == 20
                    assert bytes.fromhex(row['mixed_database']).endswith(b'|23|1800000000\n')
print('PASS: native real bind-mount updates, read-only failure, and mixed writers')
