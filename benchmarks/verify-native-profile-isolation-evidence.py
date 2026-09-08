#!/usr/bin/env python3
"""Verify native profile isolation, source identities and paired gates."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-profile-isolation-2026-09-08'
def sha(raw): return hashlib.sha256(raw).hexdigest()
for line in (OUT / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest, name
meta = json.loads((OUT / 'metadata.json').read_text())
with tarfile.open(OUT / 'inputs.tar.gz') as a:
    for name, digest in meta['source_inputs'].items(): assert sha(a.extractfile(name).read()) == digest
    raw = a.extractfile('build/zsh-sources/zsh-cad0d67c-native.json').read()
    assert sha(raw) == meta['native_lock_sha256']
    lock = json.loads(raw)
    for entry in lock['source_patches'] + lock['test_patches'] + lock['native']['sources']:
        assert sha(a.extractfile(entry['path']).read()) == entry['sha256']
manifest = json.loads(gzip.decompress((OUT / 'manifest.json.gz').read_bytes()))
files = {e['path']: e['sha256'] for e in manifest['files']}
assert files['bin/wsh'] == meta['binary_sha256'] and files['bin/wsh-runtime'] == meta['runtime_sha256']
for name, digest in meta['matched_payload'].items(): assert files[name] == digest
with tarfile.open(OUT / 'results.tar.gz') as a:
    def raw(name): return a.extractfile(name).read()
    def data(name): return json.loads(raw(name))
    def tsv(name): return list(csv.DictReader(io.StringIO(raw(name).decode()), delimiter='\t'))
    baseline = data('baseline.json')
    assert baseline['status'] == 19 and baseline['child_components_in_parent_noninteractive_profile']
    assert 'directory-jump-start' in baseline['events']
    for variant in ['normal', 'sanitized']:
        rows = data(variant + '-isolation-final/results.json')
        assert len(rows) == 7 and all(r['status'] == 19 and not r['inherited_profile_variables'] for r in rows)
        for r in rows:
            assert r['profiles'] == (2 if r['case'] == 'explicit-child-profile' else 1)
        rows = data(variant + '-test-profile-lifecycle/results.json')
        assert len(rows) == 11 and all(r['recovery_status'] == 0 for r in rows)
        rows = data(variant + '-test-profile-storage/storage-results.json')
        assert len(rows) == 9 and all(r['passed'] for r in rows)
        assert len(data(variant + '-test-profile/profile-results.json')) == 10
    assert len(data('test-startup/startup-results.json')) == 18
    assert len(data('check-installation/results.json')) == 9 and all(r['status'] == 0 for r in data('check-installation/results.json'))
    assert len(data('reader-final/report-cases.json')) == 45
    assert b'75 successful test scripts, 0 failures, 2 skipped' in raw('build-2.log')
    assert b'PASS: private end-to-end profile' in raw('legacy-profile.log')
    assert b'PASS: readiness waits' in raw('readiness-final.log')
    for theme in ['existing', 'minimal']:
        rows = tsv(theme + '-samples.tsv'); assert len(rows) == 200
        pairs = {}
        for r in rows:
            values = pairs.setdefault((r['block'], r['repetition']), {})
            assert r['variant'] not in values
            values[r['variant']] = float(r['first_editable_ms'])
        assert len(pairs) == 100 and all(set(v) == {'normal', 'profile'} for v in pairs.values())
        p90 = sorted(v['profile'] - v['normal'] for v in pairs.values())[89]
        reported = next(r for r in tsv(theme + '-summary.tsv') if r['metric'] == 'first-editable-overhead')
        assert p90 <= 3 and abs(float(reported['p90_ms']) - p90) < 1e-5
    rows = data('unprofiled-matched/samples.json'); summary = data('unprofiled-matched/summary.json')
    assert len(rows) == 200
    for theme in ['existing', 'minimal']:
        differences = []
        for pair in range(50):
            selected = [r for r in rows if r['theme'] == theme and r['pair'] == pair]
            assert [r['variant'] for r in selected] == (['control', 'native'] if pair % 2 == 0 else ['native', 'control'])
            values = {r['variant']: r['readiness_ms'] for r in selected}
            differences.append(values['native'] - values['control'])
        p95 = sorted(differences)[47]
        assert p95 <= 3 and abs(summary[theme]['paired_p95_ms'] - p95) < 1e-9
print('PASS: native profile child isolation, legacy compatibility, identities, sanitizers and matched overhead gates')
