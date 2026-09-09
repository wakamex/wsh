#!/usr/bin/env python3
"""Verify selected native helper assembly and retained contract results."""
import hashlib
import json
from pathlib import Path
import tarfile
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-qualification-2026-09-09'
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
for line in (OUT / 'runtime-SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest
meta = json.loads((OUT / 'runtime-metadata.json').read_text())
assert len(meta['helper_sha256']) == 3 and len(set(meta['helper_sha256'].values())) == 1
with tarfile.open(OUT / 'runtime-inputs.tar.gz') as a:
    for name, digest in meta['source_inputs'].items():
        assert sha(a.extractfile(name).read()) == digest
with tarfile.open(OUT / 'runtime-results.tar.gz') as a:
    def raw(name):
        return a.extractfile(name).read()
    def data(name):
        return json.loads(raw(name))
    assert sha(raw('manifest.json')) == meta['manifest_sha256']
    files = {f['path']: f for f in data('manifest.json')['files']}
    assert files['bin/wsh-runtime']['sha256'] == meta['helper_sha256']['installed']
    assert 'share/wsh/config.modules' in files and 'share/wsh/native-source-lock.json' in files
    assert b'PASS: 2237 decoder cases and 400 complete prompt/snapshot comparisons' in raw('selected-protocol.log')
    checks = data('selected-contracts/results.json')
    assert len(checks) == 9 and all(r['status'] == 0 for r in checks)
    checks = data('selected-lifecycle/results.json')
    assert len(checks) == 15 and all(r['passed'] for r in checks)
print('PASS: native C helper selection, reproducible helper builds and assembled contracts')
