#!/usr/bin/env python3
"""One-factor comparison of the retained actual configuration with its OMZ theme off."""
import argparse
import collections
import csv
import difflib
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('matrix', ROOT / 'benchmarks/benchmark-real-config.py')
matrix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matrix)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setup(work, previous, bundle, manager, output):
    work.mkdir(mode=0o700)
    os.chmod(work, 0o700)
    shutil.copytree(previous / 'fixture', work / 'fixture')
    old_metadata = json.loads((previous / 'prepared.json').read_text())
    for name, expected in old_metadata['startup_sha256'].items():
        assert sha(Path.home() / name) == expected, f'live startup file changed: {name}'
    dependencies = json.loads((previous / 'private-dependencies.json').read_text())
    for name, expected in dependencies.items():
        assert sha(Path.home() / name) == expected, f'installed dependency changed: {name}'
    original = (previous / 'actual/normal/.zshrc').read_text()
    assert original.count('ZSH_THEME="wakamex"') == 1
    candidate = original.replace('ZSH_THEME="wakamex"', 'ZSH_THEME=""', 1)
    for variant, rc in [('normal', original), ('theme-off', candidate)]:
        directory = work / 'actual' / variant
        directory.mkdir(parents=True)
        for name in ['.zshenv', '.zprofile', '.zlogin', '.zlogout']:
            source = previous / 'actual/normal' / name
            if source.exists():
                text = source.read_text().replace(old_metadata['bundle'], str(bundle))
                (directory / name).write_text(text)
        (directory / '.zshrc').write_text(rc)
    subprocess.run([manager, 'bundle', 'activate', bundle, '--state-root', work / 'state'], check=True, stdout=subprocess.DEVNULL)
    metadata = {'bundle_sha256': sha(bundle / 'manifest.json'), 'manager_sha256': sha(manager), 'runtime_sha256': sha(bundle / 'bin/wsh-runtime'), 'zsh_sha256': sha(bundle / 'bin/zsh'), 'source_revision': json.loads((bundle / 'manifest.json').read_text())['rust']['source_revision'], 'startup_sha256': old_metadata['startup_sha256'], 'dependencies_sha256': old_metadata['dependencies_sha256'], 'fixture_tree': subprocess.check_output(['git', '-C', work / 'fixture', 'rev-parse', 'HEAD^{tree}'], text=True).strip(), 'private_rc_sha256': {v: sha(work / 'actual' / v / '.zshrc') for v in ['normal', 'theme-off']}, 'common_startup_adapter': 'module/function paths rebound to selected bundle in both variants', 'single_change': 'ZSH_THEME="wakamex" -> ZSH_THEME=""', 'artifact_status': 'unsigned development artifact', 'normal_pairs': 20, 'order': '20 forward and 20 reverse pairs after five warmups per variant', 'readiness': 'shared ZLE observer then native OSC 133 B; no Wsh profiling or strace during timing', 'host_exclusivity': 'CPU 0 affinity only; other host services remain active'}
    (output / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (output / 'startup-change.diff').write_text(''.join(difflib.unified_diff(original.splitlines(keepends=True), candidate.splitlines(keepends=True), fromfile='private actual .zshrc', tofile='private actual .zshrc with OMZ theme off', n=0)))


PROBE = r'''_wsh_theme_probe() { print -nr -- $'\x1eEDIT_STATE:'${BUFFER}:$POSTDISPLAY:${#region_highlight}:$'\x1f'; }; zle -N _wsh_theme_probe; bindkey '^X^G' _wsh_theme_probe; bindkey '^X^H' history-substring-search-up'''
OWNERS = r'''print -r -- $'\x1eTHEME_STATE:'${+functions[_wakamex_git_request]}:${#${(M)precmd_functions:#_wakamex_git_request}}:${#${(M)preexec_functions:#_wakamex_prompt_preexec}}:${#${(M)zshexit_functions:#_wakamex_git_shutdown}}:${+functions[git-fetch-all]}:${+functions[update_current_git_vars]}:; [[ $PROMPT == $WSH_LAST_PROMPT ]] && print -r -- WSH_PROMPT_OWNED'''


def probe(shell):
    offset = shell.send(b'\x18\x07')
    data = shell.read_until(b'\x1f', offset)
    match = re.search(rb'\x1eEDIT_STATE:(.*?):(.*?):(\d+):\x1f', data)
    assert match, 'editor state marker missing'
    return match.groups()


def check(shell, variant):
    state = matrix.correctness(shell, 'actual', variant)
    assert state.split(':')[7:14] == ['1'] * 7, 'editing, completion, alias or language-manager state missing'
    shell.settle()
    assert b'git:main' in shell.output, 'Wsh Git prompt did not settle'
    ownership = shell.command(OWNERS)
    match = re.search(rb'\x1eTHEME_STATE:([0-9:]+)', ownership)
    assert match
    fields = match[1].decode().rstrip(':').split(':')
    assert fields[:4] == (['1'] * 4 if variant == 'normal' else ['0'] * 4), fields
    assert fields[4:] == ['1', '1'], 'unrelated configured Git functions removed'
    assert b'WSH_PROMPT_OWNED\r\n' in ownership, 'displayed prompt has another owner'
    shell.command(PROBE)
    shell.command('print -r -- WSH_THEME_HISTORY_SEED')
    shell.send('print -r -- WSH_THEME_HISTORY_')
    shell.settle(.15)
    _, suggestion, highlights = probe(shell)
    assert suggestion == b'SEED' and int(highlights) > 0
    offset = shell.send(b'\x03')
    shell.read_until(matrix.READY, offset)
    shell.send('WSH_THEME_HISTORY_')
    shell.settle(.05)
    shell.send(b'\x18\x08')
    shell.settle(.05)
    buffer, _, _ = probe(shell)
    assert buffer == b'print -r -- WSH_THEME_HISTORY_SEED'
    offset = shell.send(b'\x03')
    shell.read_until(matrix.READY, offset)
    return state, ':'.join(fields)


def summarize(output):
    rows = list(csv.DictReader((output / 'samples.tsv').open(), delimiter='\t'))
    groups = collections.defaultdict(list)
    pairs = collections.defaultdict(dict)
    for row in rows:
        if row['block'] == 'warmup':
            continue
        for metric in ['first_editable_ms', 'transition_ms']:
            value = float(row[metric])
            groups[row['variant'], metric].append(value)
            pairs[row['block'], row['repetition'], metric][row['variant']] = value
    for (_, _, metric), pair in pairs.items():
        groups['theme-off-minus-normal', metric].append(pair['theme-off'] - pair['normal'])
    with (output / 'summary.tsv').open('w') as stream:
        writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
        writer.writerow(['variant', 'metric', 'samples', 'median_ms', 'p90_ms', 'maximum_ms'])
        for (variant, metric), values in groups.items():
            writer.writerow([variant, metric, len(values), f'{statistics.median(values):.6f}', f'{sorted(values)[math.ceil(.9*len(values))-1]:.6f}', f'{max(values):.6f}'])


def export_processes(output, work, intervals):
    events = []
    for variant, interval in intervals.items():
        pending = {}
        for line in (work / f'process-{variant}.strace').read_text().splitlines():
            match = re.match(r'(\d+)\s+([0-9.]+)\s+(.*)', line)
            if not match:
                continue
            pid, stamp, syscall = match.groups()
            start = re.match(r'execve\("([^"\n]+)"', syscall)
            if start:
                pending[pid] = (float(stamp), Path(start[1]).name)
            if (start or syscall.startswith('<... execve resumed>')) and re.search(r'= 0$', syscall):
                timestamp, executable = pending.pop(pid)
                if timestamp <= interval[1]:
                    phase = 'startup' if timestamp < interval[0] else 'noop-transition'
                    events.append([variant, phase, pid, f'{timestamp:.6f}', executable])
    with (output / 'process-events.tsv').open('w') as stream:
        writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
        writer.writerow(['variant', 'phase', 'pid', 'unix_seconds', 'executable_basename'])
        writer.writerows(events)
    counts = collections.Counter((variant, phase, executable) for variant, phase, _, _, executable in events)
    with (output / 'process-counts.tsv').open('w') as stream:
        writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
        writer.writerow(['variant', 'phase', 'executable_basename', 'count'])
        for key, count in sorted(counts.items()):
            writer.writerow([*key, count])
    assert counts['normal', 'noop-transition', 'git'] - counts['theme-off', 'noop-transition', 'git'] >= 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('work', type=Path)
    parser.add_argument('previous', type=Path)
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    output, work, previous, bundle = [p.resolve() for p in [args.output, args.work, args.previous, args.bundle]]
    manager = ROOT / 'target/release/wsh'
    output.mkdir(exist_ok=True)
    setup(work, previous, bundle, manager, output)
    with (output / 'correctness.tsv').open('w') as stream:
        writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
        writer.writerow(['variant', 'startup_completion_ctrl_c_editing_prompt', 'plugin_and_hook_state', 'theme_and_preserved_git_functions'])
        for variant in ['normal', 'theme-off']:
            shell = matrix.Shell(work, bundle, manager, 'actual', variant, f'correctness-{variant}')
            try:
                state, owners = check(shell, variant)
                writer.writerow([variant, 'pass', state, owners])
                stream.flush()
                print('correctness', variant, 'pass', flush=True)
            finally:
                shell.close()
    launches = [(variant, 'warmup', i) for i in range(5) for variant in ['normal', 'theme-off']]
    launches += [(variant, block, i) for block in ['forward', 'reverse'] for i in range(20) for variant in (['normal', 'theme-off'] if block == 'forward' else ['theme-off', 'normal'])]
    with (output / 'samples.tsv').open('w') as stream:
        writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
        writer.writerow(['variant', 'block', 'repetition', 'first_editable_ms', 'transition_ms'])
        for variant, block, i in launches:
            shell = matrix.Shell(work, bundle, manager, 'actual', variant, f'timing-{variant}-{block}-{i}')
            try:
                shell.settle(.15)
                start = time.monotonic_ns()
                shell.command(':')
                transition = (time.monotonic_ns() - start) / 1e6
                shell.settle(.08)
                writer.writerow([variant, block, i, f'{shell.first_ms:.6f}', f'{transition:.6f}'])
                stream.flush()
            finally:
                shell.close()
            if i % 5 == 0:
                print('timing', variant, block, i, flush=True)
    summarize(output)
    intervals = {}
    for variant in ['normal', 'theme-off']:
        shell = matrix.Shell(work, bundle, manager, 'actual', variant, f'process-{variant}', trace=True)
        try:
            shell.settle(.4)
            start = time.time()
            shell.command(':')
            shell.settle(.4)
            intervals[variant] = [start, time.time()]
        finally:
            shell.close()
    (output / 'process-intervals.json').write_text(json.dumps(intervals, indent=2) + '\n')
    export_processes(output, work, intervals)
    print('PASS: correctness and at least one fewer Git execution per transition', flush=True)


if __name__ == '__main__':
    main()
