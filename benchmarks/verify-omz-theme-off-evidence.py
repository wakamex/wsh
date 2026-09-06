#!/usr/bin/env python3
"""Check the public OMZ counterfactual's hashes, arithmetic and ownership results."""
import collections
import csv
import hashlib
import importlib.util
from pathlib import Path
import tempfile

root = Path(__file__).resolve().parent.parent
output = root / 'benchmarks/omz-theme-off-2026-09-05'
for record in (output / 'SHA256SUMS').read_text().splitlines():
    expected, name = record.split('  ', 1)
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
spec = importlib.util.spec_from_file_location('experiment', root / 'benchmarks/benchmark-omz-theme-off.py')
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)
with tempfile.TemporaryDirectory(prefix='wsh-omz-evidence-') as scratch:
    scratch = Path(scratch)
    (scratch / 'samples.tsv').write_bytes((output / 'samples.tsv').read_bytes())
    experiment.summarize(scratch)
    assert (scratch / 'summary.tsv').read_bytes() == (output / 'summary.tsv').read_bytes()
rows = list(csv.DictReader((output / 'samples.tsv').open(), delimiter='\t'))
assert len(rows) == 90
assert collections.Counter(row['variant'] for row in rows if row['block'] != 'warmup') == {'normal': 40, 'theme-off': 40}
counts = collections.Counter((row['variant'], row['phase'], row['executable_basename']) for row in csv.DictReader((output / 'process-events.tsv').open(), delimiter='\t'))
retained = {(row['variant'], row['phase'], row['executable_basename']): int(row['count']) for row in csv.DictReader((output / 'process-counts.tsv').open(), delimiter='\t')}
assert counts == retained
assert counts['normal', 'noop-transition', 'git'] == 5
assert counts['theme-off', 'noop-transition', 'git'] == 4
assert counts['normal', 'noop-transition', 'python3'] == counts['theme-off', 'noop-transition', 'python3'] == 1
correctness = list(csv.DictReader((output / 'correctness.tsv').open(), delimiter='\t'))
assert len(correctness) == 2
for row in correctness:
    assert row['startup_completion_ctrl_c_editing_prompt'] == 'pass'
    assert row['plugin_and_hook_state'].split(':')[7:14] == ['1'] * 7
    expected = '1:1:1:1:1:1' if row['variant'] == 'normal' else '0:0:0:0:1:1'
    assert row['theme_and_preserved_git_functions'] == expected
print('PASS: 40 paired observations, summary arithmetic, one fewer Git execution, theme-hook removal, preserved Git functions, and correctness results agree')
