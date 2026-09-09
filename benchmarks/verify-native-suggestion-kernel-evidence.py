#!/usr/bin/env python3
"""Verify the three-way suggestion comparison and retained malformed-pattern case."""
import hashlib
import json
from pathlib import Path
import shlex
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-suggestion-kernel-2026-09-09'
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
for line in (OUT / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest
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
    initial = data('parity-sanitized/results.json')
    assert initial[0]['stdout'] == initial[1]['stdout'] != initial[2]['stdout']
    for directory in ('parity-final', 'parity-sanitized-final'):
        rows = data(directory + '/results.json')
        assert len(rows) == 3 and len({r['stdout'] for r in rows}) == 1
        assert all(r['status'] == 0 and not r['stderr'] for r in rows)
        assert len(bytes.fromhex(rows[0]['stdout']).splitlines()) == 6054
        assert raw(directory + '.log') == b'PASS: 6054 suggestions match across reference, builtin and C strategies\n'
    for workload, summary in data('timing/summary.json').items():
        count, query = workload.split('/', 1)
        rows = [shlex.split(line) for line in raw('timing/' + count + '.stdout').decode().splitlines()]
        assert len(rows) == 300 and not raw('timing/' + count + '.stderr')
        pairs = [{} for _ in range(50)]
        for index, q, owner, elapsed, suggestion in rows:
            if q == query:
                assert suggestion == (f'echo project {int(count) - 1}' if q == 'echo project' else '')
                pairs[int(index)][owner] = float(elapsed)
        assert pairs == summary['pairs']
        medians = {owner: statistics.median(p[owner] for p in pairs) for owner in ('control', 'quote_builtin', 'candidate')}
        assert medians == summary['median_ms']
        for owner in ('quote_builtin', 'candidate'):
            assert sorted(p[owner] - p['control'] for p in pairs)[47] == summary['paired_p95_delta_ms'][owner] <= 1
        reduction = 1 - medians['candidate'] / medians['quote_builtin']
        assert reduction == summary['c_reduction_from_builtin']
        if count == '10000':
            assert reduction >= 0.2
print('PASS: native suggestion parity, malformed-pattern behavior and three-way timing gates')
