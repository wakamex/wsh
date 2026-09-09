#!/usr/bin/env python3
"""Verify retained C theme-validator parity and matched parser timings."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-render-2026-09-08'
sha = lambda raw: hashlib.sha256(raw).hexdigest()
for line in (OUT / 'theme-parser-SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest, name
meta = json.loads((OUT / 'theme-parser-metadata.json').read_text())
with tarfile.open(OUT / 'theme-parser-inputs.tar.gz') as archive:
    for name, digest in meta['source_inputs'].items():
        assert sha(archive.extractfile(name).read()) == digest, name
    for line in archive.extractfile('third_party/tomlc17/SHA256SUMS').read().decode().splitlines():
        digest, name = line.split('  ', 1)
        assert sha(archive.extractfile('third_party/tomlc17/' + name).read()) == digest
with tarfile.open(OUT / 'theme-parser-results.tar.gz') as archive:
    def raw(name): return archive.extractfile(name).read()
    def data(name): return json.loads(raw(name))
    for name, binary in [('theme-parity-sanitized-final', 'sanitized'), ('theme-parity-release', 'c')]:
        rows = data(name + '/results.json')
        assert len(rows) == 1596 and all(row['passed'] for row in rows)
        assert sum(row['case'].startswith('mutation-') for row in rows) == 1000
        assert data(name + '/metadata.json')['binaries']['c']['sha256'] == meta['binaries'][binary]['sha256']
        for row in rows:
            c, rust = row['observed']['c'], row['observed']['rust']
            assert c['status'] in (0, 1) and (c['status'] == 0) == (rust['status'] == 0)
            assert 'Sanitizer' not in c['stderr'] and 'runtime error:' not in c['stderr']
            if not c['status']: assert c['stdout'] == rust['stdout']
    files = data('theme-file-boundaries/results.json')
    assert len(files) == 6 and all(row['passed'] for row in files)
    corpus = data('tomlc17-corpus-sanitizer.json')
    assert len(corpus) == 779 and all(row['passed'] and row['status'] in (0, 1) for row in corpus)
    units = data('tomlc17-final-unit-results.json')
    assert len(units) == 10 and all(row['status'] == 0 for row in units)
    assert b'220 passed,  0 failed' in raw('tomlc17-standard-sanitized-3.log')
    assert b'493 passed,  0 failed' in raw('tomlc17-standard-sanitized-3.log')
    assert all(row['passed'] for row in data('tomlc17-u64-parity.json'))
    assert any('runtime error:' in row['stderr'] for row in data('tomlc17-numeric-baseline.json'))
    assert all(row['status'] == 0 for row in data('tomlc17-long-integers-fixed.json'))
    samples = data('theme-parse-samples.json'); summary = data('theme-parse-summary.json')
    assert len(samples) == 16000 and len(summary) == 4
    for theme, modes in summary.items():
        for mode in ['empty', 'parse']:
            differences = []
            for pair in range(1000):
                rows = [r for r in samples if r['theme'] == theme and r['mode'] == mode and r['pair'] == pair]
                assert [r['variant'] for r in rows] == (['c', 'rust'] if pair % 2 == 0 else ['rust', 'c'])
                values = {r['variant']: r['elapsed_ns'] for r in rows}
                differences.append(values['c'] - values['rust'])
            observed = sorted(differences)[949]
            assert observed == modes[mode]['paired_p95_ns']
            if mode == 'parse': assert observed <= 500000
print('PASS: C theme parser definitions, dependency fixes, sanitizer evidence and matched parser gates')
