#!/usr/bin/env python3
"""Verify real upstream results, complete highlight parity and rejected gates."""
import hashlib
import json
from pathlib import Path
import shlex
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-highlight-kernel-2026-09-09'
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
    for result in data('upstream-results.json'):
        lines = raw('upstream-' + result['owner'] + '-final.log').decode().splitlines()
        assert result['status'] == 0
        assert sum(line.startswith('ok ') for line in lines) == result['ok'] == 1629
        assert [line for line in lines if line.startswith('not ok ')] == result['not_ok']
        assert len(result['not_ok']) == 28 and all('# TODO' in line for line in result['not_ok'])
    assert data('sanitizer-result.json')['status'] == 0 and not raw('upstream-sanitized.log')
    rows = [shlex.split(line) for line in raw('timing/stdout').decode().splitlines()]
    assert len(rows) == 800 and not raw('timing/stderr')
    summaries = data('timing/summary.json')
    for workload, summary in summaries.items():
        number, cache = workload.split('/')
        pairs = [{} for _ in range(50)]
        spans = {}
        for w, c, index, owner, ms, result in rows:
            if w == number and c == cache:
                pairs[int(index)][owner] = float(ms)
                spans.setdefault(index, {})[owner] = result
        assert all(v['control'] == v['candidate'] and v['control'] for v in spans.values())
        assert pairs == summary['pairs']
        medians = {owner: statistics.median(p[owner] for p in pairs) for owner in ('control', 'candidate')}
        assert medians == summary['median_ms']
        assert sorted(p['candidate'] - p['control'] for p in pairs)[47] == summary['paired_p95_delta_ms']
        assert 1 - medians['candidate'] / medians['control'] == summary['median_reduction']
    assert all(summaries[n]['median_reduction'] < 0.2 for n in ('2/cold', '2/warm', '3/cold', '3/warm'))
    assert any(s['paired_p95_delta_ms'] > 1 for s in summaries.values())
print('PASS: native classifier upstream suite, complete highlight parity and retained failed adoption gates')
