#!/usr/bin/env python3
"""Check module ownership, preserved external loading, startup and memory gates."""
import hashlib
import json
from pathlib import Path
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-qualification-2026-09-09'
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
for line in (OUT / 'modules-SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest
meta = json.loads((OUT / 'modules-metadata.json').read_text())
assert meta['variants']['control']['runtime_sha256'] == meta['variants']['candidate']['runtime_sha256']
with tarfile.open(OUT / 'modules-inputs.tar.gz') as archive:
    for name, digest in meta['source_inputs'].items():
        assert sha(archive.extractfile(name).read()) == digest
with tarfile.open(OUT / 'modules-results.tar.gz') as archive:
    def raw(name):
        return archive.extractfile(name).read()
    def data(name):
        return json.loads(raw(name))
    assert b'failed to load module: zsh/stat' in raw('static-build.log')
    config = raw('linked-config.modules').decode().splitlines()
    entries = [line for line in config if line.startswith('name=')]
    assert sum('link=static ' in line for line in entries) == 41
    assert not any('link=dynamic ' in line for line in entries)
    for directory in ('module-lifetime', 'module-lifetime-sanitized'):
        checks = data(directory + '/results.json')
        assert checks['passed'] and checks['status'] == 0 and not checks['stderr']
        assert checks['after'].endswith(' (deleted)')
        assert checks['stdout'] == 'WSH_LINKED_AND_EXTERNAL_OK\n'
    for directory in ('linked-startup', 'linked-startup-sanitized'):
        assert raw(directory + '.log').startswith(b'PASS: 18 native startup,')
    for directory in ('linked-contracts', 'linked-c-contracts'):
        checks = data(directory + '/results.json')
        assert len(checks) == 9 and all(r['status'] == 0 for r in checks)
    rows = data('linked-timing/samples.json')
    assert len(rows) == 200
    for theme, summary in data('linked-timing/summary.json').items():
        pairs = [{} for _ in range(50)]
        for row in rows:
            if row['theme'] == theme:
                pairs[row['pair']][row['variant']] = row['readiness_ms']
        assert sorted(p['native'] - p['control'] for p in pairs)[47] == summary['paired_p95_ms'] <= 3
        assert summary['passed']
    rows = data('linked-memory/samples.json')
    assert len(rows) == 40
    for row in rows:
        assert len(row['processes']) == 2
        for process in row['processes']:
            assert int(next(line for line in process['smaps_rollup'].splitlines() if line.startswith('Pss:')).split()[1]) == process['pss_kib']
        assert sum(p['pss_kib'] for p in row['processes']) == row['pss_kib']
    pairs = [{r['owner']: r['pss_kib'] for r in rows if r['pair'] == i} for i in range(20)]
    differences = [p['candidate'] - p['control'] for p in pairs]
    summary = data('linked-memory/summary.json')
    assert max(differences) == summary['max_delta_kib'] <= summary['limit_kib'] == 4096
    assert sorted(differences)[18] == summary['p95_delta_kib']
    assert {owner: statistics.median(p[owner] for p in pairs) for owner in ('control', 'candidate')} == summary['median_kib']
    sizes = data('module-size-libraries.json')
    assert sizes['dynamic']['needed'] == sizes['linked']['needed']
print('PASS: linked bundled modules, external loader, old-inode lifecycle and resource gates')
