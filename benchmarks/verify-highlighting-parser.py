#!/usr/bin/env python3
"""Preserve the rejected parser experiment without treating failures as adoption."""
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[1]
evidence = root / 'benchmarks/native-consolidation-2026-09-10'
identity = json.loads((evidence / 'highlighting-identity.json').read_text())
archive = evidence / 'highlighting-evidence.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == identity['archive_sha256']
assert identity['selected'] is False
with tarfile.open(archive) as t:
    for name, digest in identity['files'].items():
        data = t.extractfile(name).read()
        assert hashlib.sha256(data).hexdigest() == digest, name
        if name.startswith('highlight-corpus-qualified-sanitized/') and name.endswith('.log'):
            assert b'AddressSanitizer' not in data and b'runtime error:' not in data, name
    def read(name):
        return json.load(t.extractfile(name))
    for directory in ('highlight-corpus-qualified', 'highlight-corpus-qualified-sanitized'):
        rows = read(directory + '/results.json')
        summary = read(directory + '/summary.json')
        assert len(rows) == 574
        for owner, passing in (('control', 287), ('candidate', 133)):
            selected = [r for r in rows if r['owner'] == owner]
            assert len(selected) == len({r['case'] for r in selected}) == 287
            assert sum(r['passed'] for r in selected) == passing
            assert summary[owner] == dict(cases=287, passed=passing)
        main = [r for r in rows if r['owner'] == 'candidate' and r['case'].startswith('main/')]
        assert len(main) == 271 and sum(r['passed'] for r in main) == 117
    for directory in ('highlight-parser-final-zle', 'highlight-parser-final-zle-sanitized', 'highlight-parser-compact-zle'):
        rows = read(directory + '/correctness.json')['workloads']
        assert set(rows) == {'short', 'repeated', 'distinct', 'multiline'}
        for name, row in rows.items():
            equal = bool(row['regions']['control']) and row['regions']['control'] == row['regions']['candidate']
            assert equal == row['equal'] == (name != 'multiline')
    failure = t.extractfile('highlight-parser-compact-measure.log').read()
    assert b'AssertionError' in failure and b"('short'," in failure
    assert 'highlight-parser-compact-zle/measure.json' not in identity['files']
print('PASS: retained highlighting parser rejection, full corpus and composed-region failures')
