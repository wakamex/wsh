#!/usr/bin/env python3
"""Verify relocation ownership, full contracts and matched native readiness."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-qualification-2026-09-09'
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
for line in (OUT / 'paths-SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest
meta = json.loads((OUT / 'paths-metadata.json').read_text())
assert meta['variants']['control']['runtime_sha256'] == meta['variants']['candidate']['runtime_sha256']
with tarfile.open(OUT / 'paths-inputs.tar.gz') as archive:
    for name, digest in meta['source_inputs'].items():
        assert sha(archive.extractfile(name).read()) == digest
with tarfile.open(OUT / 'paths-results.tar.gz') as archive:
    def raw(name):
        return archive.extractfile(name).read()
    def data(name):
        return json.loads(raw(name))
    assert b'/var/tmp/wsh-rust-git-pipe-build/' in raw('paths-baseline.stdout')
    for directory in ('paths-check', 'paths-sanitized-check'):
        checks = data(directory + '/results.json')
        assert checks['passed'] and checks['missing_function_status'] != 0
        assert 'function definition file not found' in checks['missing_function_stderr']
        assert '/usr/local/share/zsh/site-functions' in checks['defaults']
        assert not any('/wsh-native-qualified-paths-final/' in p or '/wsh-native-entry-prototype/install/' in p for p in checks['defaults'])
        assert b'PASS:' in raw(directory + '.log')
    for directory in ('startup', 'startup-sanitized'):
        assert raw(directory + '.log').startswith(b'PASS: 18 native startup,')
    for directory in ('contracts', 'c-contracts'):
        checks = data(directory + '/results.json')
        assert len(checks) == 9 and all(r['status'] == 0 for r in checks)
    rows = data('paths-timing/samples.json')
    assert len(rows) == 200
    for theme, summary in data('paths-timing/summary.json').items():
        pairs = [{} for _ in range(50)]
        for row in rows:
            if row['theme'] == theme:
                pairs[row['pair']][row['variant']] = row['readiness_ms']
        assert sorted(p['native'] - p['control'] for p in pairs)[47] == summary['paired_p95_ms'] <= 3
        assert summary['passed'] and summary['pairs'] == 50
print('PASS: native resource relocation, explicit user FPATH, full contracts and readiness gates')
