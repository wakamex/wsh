#!/usr/bin/env python3
"""Verify retained arithmetic and replay default traces through Wsh's real parser."""
import collections
import csv
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

root = Path(__file__).resolve().parent.parent
output = root / 'benchmarks/real-config-2026-09-05'
manager = root / 'target/release/wsh'
inputs = json.loads((output / 'inputs.json').read_text())
bundle = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(inputs['bundle'])
assert hashlib.sha256(gzip.decompress((output / 'bundle-manifest.json.gz').read_bytes())).hexdigest() == inputs['bundle_sha256']
for record in (output / 'SHA256SUMS').read_text().splitlines():
    expected, name = record.split('  ', 1)
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
spec = importlib.util.spec_from_file_location('summary', root / 'benchmarks/summarize-real-config.py')
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)
with tempfile.TemporaryDirectory(prefix='wsh-real-config-verify-') as scratch:
    scratch = Path(scratch)
    (scratch / 'timing.tsv').write_bytes((output / 'timing.tsv').read_bytes())
    (scratch / 'control.tsv').write_bytes((output / 'control.tsv').read_bytes())
    summary.summarize(scratch)
    for name in ['summary.tsv', 'gates.tsv', 'control-summary.tsv']:
        assert (scratch / name).read_bytes() == (output / name).read_bytes(), name
    samples = list(csv.DictReader((output / 'summary.tsv').open(), delimiter='\t'))
    assert len(samples) == 27 and all(row['samples'] == '40' for row in samples)
    expected_spans = {(row['config'], row['sample'], row['span_or_milestone']): float(row['milliseconds']) for row in csv.DictReader((output / 'spans.tsv').open(), delimiter='\t')}
    observed_spans = {}
    session = scratch / 'profile'
    session.mkdir(mode=0o700)
    (session / 'metadata.json').write_text(json.dumps({'schema_version': 1, 'bundle_root': str(bundle.resolve()), 'bundle_sha256': inputs['bundle_sha256']}))
    os.chmod(session / 'metadata.json', 0o600)
    with tarfile.open(output / 'profile-traces.tar.gz') as archive:
        members = archive.getmembers()
        assert len(members) == 360
        for member in members:
            assert member.isfile() and '/' not in member.name
            config, sample = member.name.removeprefix('timing-').removesuffix('.jsonl').split('-profile-', 1)
            (session / 'trace.jsonl').write_bytes(archive.extractfile(member).read())
            os.chmod(session / 'trace.jsonl', 0o600)
            report = subprocess.check_output([manager, 'profile', 'report', session], text=True)
            # Historical reports used broader labels for the same trace events.
            report = report.replace('Wsh ZLE initialization hook:', 'First editable prompt:').replace('Wsh first precmd hook:', 'First precmd:')
            for field, value in re.findall(r'^([^\n:]+): ([0-9.]+) ms$', report, re.M):
                observed_spans[config, sample, field] = float(value)
    assert observed_spans == expected_spans, 'retained spans disagree with production trace parser'
    grouped = collections.defaultdict(list)
    for (config, _, field), value in expected_spans.items():
        grouped[config, field].append(value)
    import statistics
    for row in csv.DictReader((output / 'span-summary.tsv').open(), delimiter='\t'):
        values = grouped[row['config'], row['span_or_milestone']]
        assert len(values) == int(row['samples'])
        assert round(statistics.median(values), 3) == float(row['median_ms'])
counts = collections.Counter((row['config'], row['variant'], row['phase'], row['executable_basename']) for row in csv.DictReader((output / 'process-events.tsv').open(), delimiter='\t'))
expected_counts = {(row['config'], row['variant'], row['phase'], row['executable_basename']): int(row['count']) for row in csv.DictReader((output / 'process-counts.tsv').open(), delimiter='\t')}
assert counts == expected_counts
editing = list(csv.DictReader((output / 'editing.tsv').open(), delimiter='\t'))
assert len(editing) == 12 and all(row['result'] == 'pass' for row in editing)
print('PASS: hashes, 1,080 timing samples, summaries, 360 production-parser trace replays, component spans, process counts, and 12 editing results agree. The recorded profiling-overhead gates remain failed.')
