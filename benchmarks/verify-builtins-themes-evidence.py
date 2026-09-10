#!/usr/bin/env python3
"""Recompute retained directory-jump and renderer measurements and profiling gates."""
import csv
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
out = root / 'benchmarks/builtins-themes-2026-09-05'
for line in (out / 'SHA256SUMS').read_text().splitlines():
    expected, name = line.split('  ', 1)
    data = (subprocess.check_output(['git', '-C', str(root), 'show', '4dafee9cb740677a50f8fe22677235089c7b311d:' + name])
            if name in ('build/build-development-bundle.zsh', 'benchmarks/verify-builtins-themes-evidence.py', 'integration/integration.zsh', 'integration/directory-jump.zsh', 'crates/wsh-runtime/src/lib.rs') else (root / name).read_bytes())
    assert hashlib.sha256(data).hexdigest() == expected, name

pairs = {}
for r in csv.DictReader((out / 'accepted-directory-samples.tsv').open(), delimiter='\t'):
    key = (r['block'], r['repetition'])
    pair = pairs.setdefault(key, {})
    assert r['variant'] in ('enabled', 'disabled') and r['variant'] not in pair
    pair[r['variant']] = float(r['first_editable_ms'])
    assert float(r['settled_ms']) >= pair[r['variant']]
assert len(pairs) == 100 and all(set(p) == {'enabled', 'disabled'} for p in pairs.values())
values = sorted(p['enabled'] - p['disabled'] for p in pairs.values())
summary = dict(pairs=100, median_extra_ms=statistics.median(values), p90_extra_ms=values[89], limit_ms=3, **{'pass': values[89] <= 3})
assert summary == json.loads((out / 'accepted-directory-summary.json').read_text()) and summary['pass']

render_summary = {}
for theme in ('minimal', 'wakamex', 'robbyrussell', 'agnoster'):
    events = [json.loads(line) for line in (out / f'render-traces/{theme}.jsonl').read_text().splitlines()]
    spans = [e['render_duration_us'] for e in events if e['event'] == 'snapshot-published']
    assert len(spans) == 60 and all(v >= 0 for v in spans)
    render_summary[theme] = dict(samples=60, median_us=statistics.median(spans), p90_us=sorted(spans)[53], maximum_us=max(spans))
assert render_summary == json.loads((out / 'render-traces/summary.json').read_text())

with tempfile.TemporaryDirectory(prefix='wsh-builtins-evidence-') as tmp:
    summary_path = Path(tmp) / 'profile.tsv'
    subprocess.run([str(root / 'benchmarks/summarize-profile.zsh'), str(out / 'accepted-profile-samples.tsv'), str(summary_path)], check=True, stdout=subprocess.DEVNULL)
    assert summary_path.read_bytes() == (out / 'accepted-profile-summary.tsv').read_bytes()
    gates = subprocess.check_output([str(root / 'benchmarks/check-profile-gates.zsh'), str(summary_path), str(out / 'runtime-trace.tsv')])
    assert gates == (out / 'accepted-profile-gates.tsv').read_bytes()

correctness = (out / 'final-omz-directory-jump.log').read_text()
for owner in ('builtin', 'external', 'custom', 'executable', 'disabled', 'omz'):
    assert f'PASS: {owner} directory-jump ownership and behavior' in correctness
assert 'PASS: real ZLE completion handles spaces' in correctness
assert 'PASS: directory database persists' in correctness
for theme in ('minimal', 'wakamex', 'robbyrussell', 'agnoster'):
    assert f'PASS: {theme} resolves' in (out / 'final-named-themes.log').read_text()
print('PASS: source hashes, directory-jump ownership, four themes, 100-pair startup and profiling gates, runtime tracing and 240 renderer spans agree')
