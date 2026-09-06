#!/usr/bin/env python3
"""Attribute first-Tab time with buffered clocks and matched controls."""
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import time

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[1]
OUT = Path('/var/tmp/wsh-completion-costs-2026-09-06')
PREVIOUS = ROOT / 'benchmarks/deferred-completion-2026-09-06'
spec = importlib.util.spec_from_file_location('completion_fixture', PREVIOUS / 'run.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.OUT = OUT
EXPORT = r'''
zmodload zsh/datetime
typeset -ga _COST_TIMES=()
_cost_export() { print -nr -- $'\x1eCOST:'"${_DEFERRED_RUNS:-0}|${(j:,:)_COST_TIMES}"$'\x1f'; }
zle -N _cost_export
bindkey '^V' _cost_export
'''
base.CONFIG += EXPORT
STAGES = ['autoload', 'compinit', 'directory_jump', 'tab_delegate', 'autosuggestion_rebind', 'native_completion']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def instrument():
    text = (PREVIOUS / 'deferred.zsh').read_text()
    replacements = [
        ('      autoload -Uz compinit\n', '      _COST_TIMES=($EPOCHREALTIME)\n      autoload -Uz compinit\n      _COST_TIMES+=($EPOCHREALTIME)\n'),
        ('      compinit -i -d "$HOME/.zcompdump" || return\n', '      compinit -i -d "$HOME/.zcompdump" || return\n      _COST_TIMES+=($EPOCHREALTIME)\n'),
        ('      if [[ $WSH_DIRECTORY_JUMP_OWNER == wsh &&', '      _COST_TIMES+=($EPOCHREALTIME)\n      if [[ $WSH_DIRECTORY_JUMP_OWNER == wsh &&'),
        ('      if [[ $WSH_AUTOSUGGESTIONS_OWNER == wsh ]]; then', '      _COST_TIMES+=($EPOCHREALTIME)\n      if [[ $WSH_AUTOSUGGESTIONS_OWNER == wsh ]]; then'),
        ('      zle expand-or-complete\n', '      _COST_TIMES+=($EPOCHREALTIME)\n      zle expand-or-complete\n      _COST_TIMES+=($EPOCHREALTIME)\n'),
    ]
    for old, new in replacements:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text

def export(shell):
    offset = len(shell.output)
    os.write(shell.fd, b'\x16')
    shell.wait(b'\x1f', offset)
    start = shell.output.index(b'\x1eCOST:', offset) + len(b'\x1eCOST:')
    end = shell.output.index(b'\x1f', start)
    count, values = shell.output[start:end].decode().split('|')
    assert count == '1', count
    return values.split(',') if values else []

def observe(variant, label):
    shell = base.Shell(variant, label)
    try:
        branch, first = shell.complete('git switch wsh-native-')
        second, second_ms = shell.complete('git switch wsh-native-')
        assert branch == second == 'git switch wsh-native-completion-unique ', (branch, second)
        clocks = export(shell)
        timed = '-timed-' in variant
        assert len(clocks) == (7 if timed else 0), clocks
        row = {'variant': variant, 'startup_ms': shell.startup_ms, 'first_tab_ms': first,
               'second_tab_ms': second_ms, 'buffer': branch, 'clocks': clocks}
        if timed:
            # Retain decimal strings; compute intervals without epoch-sized float cancellation.
            from decimal import Decimal
            times = [Decimal(t) for t in clocks]
            spans = [float((b - a) * 1000) for a, b in zip(times, times[1:])]
            assert all(v >= 0 for v in spans), spans
            total = float((times[-1] - times[0]) * 1000)
            assert 0 < total <= first, (total, first)
            row.update(spans_ms=dict(zip(STAGES, spans)), internal_ms=total, outer_ms=first-total)
        return row
    finally:
        shell.close()

def prepare():
    previous = json.loads((PREVIOUS / 'metadata.json').read_text())
    assert sha(PREVIOUS / 'run.py') == previous['harness_sha256']
    assert sha(PREVIOUS / 'deferred.zsh') == previous['prototype_sha256']
    base.prepare()
    prototype = instrument()
    (OUT / 'instrumented.zsh').write_text(prototype)
    for home in (OUT / 'work').iterdir():
        if (home / '.zshrc').is_file():
            (home / 'deferred.zsh').write_text(prototype)
    metadata = json.loads((OUT / 'metadata.json').read_text())
    metadata.update(harness_sha256=sha(SOURCE / 'run.py'), plan_sha256=sha(SOURCE / 'plan.md'),
                    prototype_sha256=sha(OUT / 'instrumented.zsh'),
                    reused_harness_sha256=sha(PREVIOUS / 'run.py'),
                    control_prototype_sha256=sha(PREVIOUS / 'deferred.zsh'),
                    trace_mode='buffered component clocks versus unchanged control; shared datetime preload',
                    command='python3 ' + str(SOURCE / 'run.py') + ' correctness; python3 ' + str(SOURCE / 'run.py') + ' measure')
    (OUT / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    base.correctness()
    probes = []
    for cache in ('cold', 'warm'):
        for mode in ('control', 'timed'):
            variant = 'deferred-' + mode + '-' + cache
            home = OUT / 'work' / variant
            home.mkdir(mode=0o700)
            (home / '.zshrc').write_text(base.CONFIG)
            (home / 'jump-data').write_bytes((OUT / 'work/deferred-warm/jump-data').read_bytes())
            (home / 'deferred.zsh').write_text(prototype if mode == 'timed' else (PREVIOUS / 'deferred.zsh').read_text())
            probes.append(observe(variant, 'clock-check-' + variant))
    (OUT / 'clock-checks.json').write_text(json.dumps(probes, indent=2) + '\n')
    print('PASS: component clocks are ordered, fit the parent interval, and record one initialization', flush=True)

def percentile(values, p):
    return sorted(values)[math.ceil(len(values) * p / 100) - 1]

def summarize(rows):
    summary = {}
    for cache in ('cold', 'warm'):
        group = [r for r in rows if r['cache'] == cache]
        pairs = [{r['mode']: r for r in group if r['round'] == i} for i in range(50)]
        overhead = [p['timed']['first_tab_ms'] - p['control']['first_tab_ms'] for p in pairs]
        item = {'pairs': len(pairs), 'paired_overhead_p95_ms': percentile(overhead, 95),
                'paired_overhead_median_ms': percentile(overhead, 50),
                'instrumentation_gate': percentile(overhead, 95) <= 3, 'variants': {}, 'stages': {}}
        for mode in ('control', 'timed'):
            selected = [r for r in group if r['mode'] == mode]
            item['variants'][mode] = {metric: {str(p): percentile([r[metric] for r in selected], p) for p in (50, 95)}
                                       for metric in ('startup_ms', 'first_tab_ms', 'second_tab_ms')}
        selected = [r for r in group if r['mode'] == 'timed']
        for stage in STAGES + ['internal_ms', 'outer_ms']:
            values = [r['spans_ms'][stage] if stage in STAGES else r[stage] for r in selected]
            item['stages'][stage] = {str(p): percentile(values, p) for p in (50, 95)}
        summary[cache] = item
    return summary

def measure():
    rows = []
    host = {'before': Path('/proc/stat').read_text(), 'load_before': Path('/proc/loadavg').read_text(), 'started': time.time()}
    try:
        for index in range(50):
            caches = ['cold', 'warm'] if index % 2 == 0 else ['warm', 'cold']
            modes = ['control', 'timed'] if index % 2 == 0 else ['timed', 'control']
            for cache in caches:
                for mode in modes:
                    variant = 'deferred-' + mode + '-' + cache
                    if cache == 'cold':
                        (OUT / 'work' / variant / '.zcompdump').unlink(missing_ok=True)
                    row = observe(variant, str(index) + '-' + variant)
                    row.update(round=index, cache=cache, mode=mode)
                    rows.append(row)
            if index % 10 == 9:
                print('Completed rounds:', index + 1, flush=True)
    finally:
        (OUT / 'samples.json').write_text(json.dumps(rows, indent=2) + '\n')
        host.update(after=Path('/proc/stat').read_text(), load_after=Path('/proc/loadavg').read_text(), ended=time.time())
        (OUT / 'host.json').write_text(json.dumps(host, indent=2) + '\n')
    summary = summarize(rows)
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)

if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['correctness']:
        prepare()
    elif sys.argv[1:] == ['measure']:
        measure()
    else:
        raise SystemExit('usage: run.py correctness|measure')
