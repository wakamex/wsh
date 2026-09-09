#!/usr/bin/env python3
"""Check actual reference parity and reconstruct the retained lookup gates."""
import hashlib
import json
from pathlib import Path
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-history-kernel-2026-09-09'
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
for line in (OUT / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest, name
meta = json.loads((OUT / 'metadata.json').read_text())
with tarfile.open(OUT / 'inputs.tar.gz') as archive:
    for name, digest in meta['source_inputs'].items():
        assert sha(archive.extractfile(name).read()) == digest
    for name, digest in meta['configured_headers'].items():
        assert sha(archive.extractfile('configured-zsh/' + name).read()) == digest
with tarfile.open(OUT / 'results.tar.gz') as archive:
    def raw(name):
        return archive.extractfile(name).read()
    def data(name):
        return json.loads(raw(name))
    assert sha(raw('native-manifest.json')) == meta['bundle_sha256']
    initial = data('parity/results.json')
    assert any(not row['equal'] for row in initial)
    assert b'null pointer' in raw('parity-sanitized/candidate-0-1.stderr')
    for directory in ('parity-final', 'parity-sanitized-final'):
        rows = data(directory + '/results.json')
        assert len(rows) == 4
        for row in rows:
            assert row['equal'] and row['results'][0] == row['results'][1]
            assert row['results'][0]['status'] == 0 and not row['results'][0]['stderr']
            assert len(bytes.fromhex(row['results'][0]['stdout']).splitlines()) >= 110
        assert raw(directory + '.log') == b'PASS: four history modes, 440 lazy transitions, live history and exact state parity\n'
    for count, summary in data('timing-final/summary.json').items():
        rows = [line.split() for line in raw('timing-final/' + count + '.stdout').decode().splitlines()]
        assert len(rows) == 100 and not raw('timing-final/' + count + '.stderr')
        pairs = [{} for _ in range(50)]
        for index, owner, elapsed in rows:
            pairs[int(index)][owner] = float(elapsed)
        assert pairs == summary['pairs']
        medians = {owner: statistics.median(p[owner] for p in pairs) for owner in ('control', 'candidate')}
        assert medians == summary['median_ms']
        assert sorted(p['candidate'] - p['control'] for p in pairs)[47] == summary['paired_p95_delta_ms'] <= 1
        assert 1 - medians['candidate'] / medians['control'] == summary['median_reduction']
        if count == '10000':
            assert summary['median_reduction'] >= 0.2
print('PASS: native history lazy-filter parity, retained initial failure and real-record timing gates')
