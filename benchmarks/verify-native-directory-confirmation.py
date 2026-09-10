#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parent/'native-directory-final-2026-09-10'
identity = json.loads((root/'confirmation-identity.json').read_text())
archive = root/'confirmation.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
with tarfile.open(archive) as t:
    for path, digest in identity['source'].items():
        assert hashlib.sha256(t.extractfile(path).read()).hexdigest() == digest
    for mode in ('normal', 'sanitized'):
        rows = json.load(t.extractfile('confirmation-'+mode+'/results.json'))
        assert len(rows) == 8
        for action in ('yes', 'no', 'interrupt', 'no-tty'):
            pair = [r for r in rows if r['action'] == action]
            assert [r['owner'] for r in pair] == ['control', 'candidate']
            assert pair[0]['database'] == pair[1]['database']
            assert pair[0]['status'] == pair[1]['status']
            if action != 'no-tty':
                assert all(r['prompted'] and r['lock_status'] == 0 for r in pair)
                assert pair[0]['transcript'] == pair[1]['transcript']
            assert (pair[0]['database'] == '0a') == (action == 'yes')
print('PASS: native directory confirmation, rejection, interruption, and unlocked prompt evidence')
