#!/usr/bin/env python3
"""Check the retained renderer parity and fixed paired timing gate."""
import hashlib
import json
from pathlib import Path
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-render-2026-09-08'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

for line in (OUT / 'renderer-SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest, name
meta = json.loads((OUT / 'renderer-metadata.json').read_text())
with tarfile.open(OUT / 'renderer-inputs.tar.gz') as archive:
    for name, digest in meta['source_inputs'].items():
        assert sha(archive.extractfile(name).read()) == digest, name
    for library in ['tomlc17', 'yyjson']:
        prefix = 'third_party/' + library + '/'
        for line in archive.extractfile(prefix + 'SHA256SUMS').read().decode().splitlines():
            digest, name = line.split('  ', 1)
            assert sha(archive.extractfile(prefix + name).read()) == digest
with tarfile.open(OUT / 'renderer-results.tar.gz') as archive:
    def raw(name):
        return archive.extractfile(name).read()
    def data(name):
        return json.loads(raw(name))
    for name in ['render-parity-expanded', 'render-parity-release']:
        rows = data(name + '.json')
        assert len(rows) == 45600 and all(r['passed'] for r in rows)
        assert len({r['theme'] for r in rows}) == 26
        log = raw(name + '.log')
        assert b'test result: ok. 1 passed' in log
        assert b'Sanitizer' not in log and b'runtime error:' not in log
    assert b'100% tests passed, 0 tests failed out of 12' in raw('yyjson-tests.log')
    rows = data('render-samples.json')
    summary = data('render-summary.json')
    assert len(rows) == 4000 and set(summary) == {'minimal', 'wakamex', 'robbyrussell', 'agnoster'}
    for theme, values in summary.items():
        samples = [r for r in rows if r['theme'] == theme]
        assert [r['case'] for r in samples] == list(range(1, 1001))
        assert all(r['passed'] and r['c_first'] == (r['case'] % 2 == 0) for r in samples)
        for key in ['rust_ns', 'c_ns', 'rust_empty_ns', 'c_empty_ns']:
            assert statistics.median(r[key] for r in samples) == values[key]
        difference = sorted(r['c_ns'] - r['rust_ns'] for r in samples)[949]
        assert difference == values['paired_p95_ns'] and difference <= 50000
        assert sorted(r['c_empty_ns'] - r['rust_empty_ns'] for r in samples)[949] == values['empty_p95_ns']
print('PASS: C renderer byte parity, upstream JSON sanitizer suite and paired rendering gates')
