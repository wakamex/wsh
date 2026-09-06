#!/usr/bin/env python3
"""Compare eager and first-Tab native completion using actual ZLE."""
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import pty
import select
import shlex
import signal
import subprocess
import time

SOURCE = Path(__file__).resolve().parent
OUT = Path('/var/tmp/wsh-deferred-completion-2026-09-06')
ROOT = Path('/code/wsh')
BUNDLE = ROOT / 'bundles/ccf3c17708aae1b1fc23c4170d54ff6e78a919f0adc0e0950f3590c6325c9698'
MANAGER = ROOT / 'target/release/wsh'
READY = b'\x1b]133;B\x1b\\'
CAPTURE = b'\x1eBUFFER:'
VARIANTS = ('baseline', 'eager-cold', 'eager-warm', 'deferred-cold', 'deferred-warm')
CONFIG = r'''
PROMPT='COMP> '
HISTFILE=$HOME/history
SAVEHIST=0
ZSHZ_DATA=$HOME/jump-data
[[ $COMP_CASE == vi ]] && bindkey -v
if [[ $COMP_CASE == eager-* || $COMP_CASE == existing ]]; then
  autoload -Uz compinit
  compinit -i -d "$HOME/.zcompdump"
fi
if [[ $COMP_CASE == custom-tab ]]; then
  _custom_tab() { BUFFER+='CUSTOMTAB'; CURSOR=$#BUFFER; }
  zle -N _custom_tab
  bindkey '^I' _custom_tab
fi
if [[ $COMP_CASE == deferred-* || $COMP_CASE == existing || $COMP_CASE == custom-tab || $COMP_CASE == vi || $COMP_CASE == z-first ]]; then
  source "$HOME/deferred.zsh"
fi
print -s 'print -r -- DEFER_AUTOSUGGEST_COMPLETE'
_state() {
  print -nr -- $'\x1eSTATE:'"$POSTDISPLAY|${#region_highlight}|${+functions[compdef]}|${_DEFERRED_RUNS:-0}|$WSH_AUTOSUGGESTIONS_OWNER|$WSH_SYNTAX_HIGHLIGHTING_OWNER|${_comps[z]:-}|$(bindkey '^I')"$'\x1f'
}
_custom() { BUFFER+='CUSTOM'; CURSOR=$#BUFFER; }
zle -N _state
zle -N _custom
bindkey '^T' _state
bindkey '^X' _custom
_capture() {
  print -nr -- $'\x1eBUFFER:'"$BUFFER"$'\x1f'
  BUFFER=''
  POSTDISPLAY=''
  CURSOR=0
  zle redisplay
}
zle -N _capture
bindkey '^G' _capture
'''

def run(*args):
    return subprocess.check_output([str(a) for a in args], stderr=subprocess.STDOUT)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class Shell:
    def __init__(self, variant, label):
        self.label = label
        self.output = bytearray()
        self.home = OUT / 'work' / variant
        env = {k: v for k, v in os.environ.items() if not k.startswith(('WSH_', 'WAKTERM_', 'ZSH_')) and k not in ('FPATH', 'ZDOTDIR', 'ZSH', 'ZSH_CUSTOM', 'TMUX', 'TMUX_PANE')}
        env.update(HOME=str(self.home), ZDOTDIR=str(self.home), WSH_STATE_ROOT=str(OUT / 'work/state'), WSH_THEME='', TERM='xterm-256color', LC_ALL='C.UTF-8', COMP_CASE=variant)
        self.started = time.monotonic_ns()
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.chdir(OUT / 'work/fixture')
            os.sched_setaffinity(0, {0})
            os.execve(str(MANAGER), [str(MANAGER), 'run', '--', '-di'], env)
        self.wait(READY)
        self.startup_ms = (time.monotonic_ns() - self.started) / 1e6

    def wait(self, marker, offset=0):
        deadline = time.monotonic() + 10
        while marker not in self.output[offset:]:
            if time.monotonic() >= deadline:
                raise RuntimeError('timeout: ' + self.label + repr(self.output[-2000:]))
            if select.select([self.fd], [], [], 0.1)[0]:
                self.output.extend(os.read(self.fd, 65536))

    def complete(self, text):
        return self.capture(text.encode() + b'\t')

    def capture(self, keys):
        offset = len(self.output)
        started = time.monotonic_ns()
        os.write(self.fd, keys + b'\x07')
        self.wait(b'\x1f', offset)
        elapsed = (time.monotonic_ns() - started) / 1e6
        start = self.output.index(CAPTURE, offset) + len(CAPTURE)
        end = self.output.index(b'\x1f', start)
        return self.output[start:end].decode(), elapsed

    def state(self):
        offset = len(self.output)
        os.write(self.fd, b'\x14')
        self.wait(b'\x1f', offset)
        start = self.output.index(b'\x1eSTATE:', offset) + len(b'\x1eSTATE:')
        end = self.output.index(b'\x1f', start)
        return self.output[start:end].decode().split('|')

    def close(self):
        os.kill(self.pid, signal.SIGHUP)
        os.waitpid(self.pid, 0)
        os.close(self.fd)
        with gzip.open(OUT / 'transcripts' / (self.label + '.gz'), 'wb') as stream:
            stream.write(self.output)

def prepare():
    OUT.mkdir(mode=0o700)
    work = OUT / 'work'
    work.mkdir(mode=0o700)
    (OUT / 'transcripts').mkdir()
    fixture = work / 'fixture'
    fixture.mkdir()
    (fixture / 'path with spaces').mkdir()
    (fixture / 'project alpha').mkdir()
    run('git', '-C', fixture, 'init', '-q', '-b', 'main')
    run('git', '-C', fixture, '-c', 'user.name=Completion test', '-c', 'user.email=test@wsh.invalid', 'commit', '--allow-empty', '-qm', 'seed')
    run('git', '-C', fixture, 'branch', 'wsh-native-completion-unique')
    run(MANAGER, 'bundle', 'activate', BUNDLE, '--state-root', work / 'state')
    for variant in (*VARIANTS, 'existing', 'custom-tab', 'vi', 'z-first'):
        home = work / variant
        home.mkdir(mode=0o700)
        (home / '.zshrc').write_text(CONFIG)
        (home / 'deferred.zsh').write_bytes((SOURCE / 'deferred.zsh').read_bytes())
        (home / 'jump-data').write_text(str(fixture / 'project alpha') + '|10|' + str(int(time.time())) + '\n')
    manifest = json.loads((BUNDLE / 'manifest.json').read_text())
    metadata = {'manager_source': run('git', '-C', ROOT, 'rev-parse', 'HEAD').decode().strip(), 'manager_sha256': sha(MANAGER), 'bundle_path': str(BUNDLE), 'bundle_sha256': sha(BUNDLE / 'manifest.json'), 'zsh_sha256': sha(BUNDLE / 'bin/zsh'), 'runtime_sha256': sha(BUNDLE / 'bin/wsh-runtime'), 'trace_mode': 'off', 'theme': '', 'editing_defaults': 'all enabled', 'host': run('uname', '-a').decode().strip(), 'cpu': 0, 'command': 'python3 ' + str(OUT / 'run.py'), 'config_sha256': hashlib.sha256(CONFIG.encode()).hexdigest(), 'harness_sha256': sha(Path(__file__)), 'plan_sha256': sha(SOURCE / 'plan.md'), 'git_version': run('git', '--version').decode().strip()}
    previous = json.loads((ROOT / 'benchmarks/native-completion-2026-09-06/metadata.json').read_text())
    for key in ('manager_sha256', 'bundle_sha256', 'zsh_sha256', 'runtime_sha256'):
        assert metadata[key] == previous[key], key
    metadata['manager_source'] = previous['manager_source']
    metadata['experiment_source'] = run('git', '-C', ROOT, 'rev-parse', 'HEAD').decode().strip()
    metadata['plan_sha256'] = sha(SOURCE / 'plan.md')
    metadata['prototype_sha256'] = sha(SOURCE / 'deferred.zsh')
    metadata['command'] = 'python3 ' + str(SOURCE / 'run.py') + ' correctness; python3 ' + str(SOURCE / 'run.py') + ' measure'
    (OUT / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    with gzip.open(OUT / 'bundle-manifest.json.gz', 'wb') as stream:
        stream.write((BUNDLE / 'manifest.json').read_bytes())

def correctness():
    results = []
    for variant in (*VARIANTS, 'existing', 'custom-tab', 'vi', 'z-first'):
        shell = Shell(variant, 'correctness-' + variant)
        try:
            before = shell.state()
            if variant == 'custom-tab':
                custom, _ = shell.complete('x')
                assert custom == 'xCUSTOMTAB', custom
                after = shell.state()
                assert after[2:4] == ['0', '0'], after
                results.append({'variant': variant, 'before': before, 'after': after, 'custom': custom})
                continue
            if variant == 'z-first':
                first_jump, _ = shell.complete('z alpha')
                assert shlex.split(first_jump) == ['z', str(OUT / 'work/fixture/project alpha')], first_jump
            branch, _ = shell.complete('git switch wsh-native-')
            jump, _ = shell.complete('z alpha')
            path, _ = shell.complete('cd path')
            second, _ = shell.complete('git switch wsh-native-')
            after = shell.state()
            row = {'variant': variant, 'branch': branch, 'jump': jump, 'path': path, 'second': second, 'before': before, 'after': after}
            if variant == 'z-first':
                row['first_jump'] = first_jump
            if variant in ('eager-warm', 'z-first'):
                multiword, _ = shell.complete('z project alpha')
                assert shlex.split(multiword) == ['z', 'project alpha'], multiword
                row['multiword'] = multiword
            results.append(row)
            if variant == 'baseline':
                assert branch.strip() == 'git switch wsh-native-', row
                assert jump.strip() == 'z alpha', row
            else:
                assert shlex.split(branch) == ['git', 'switch', 'wsh-native-completion-unique'], row
                assert shlex.split(jump) == ['z', str(OUT / 'work/fixture/project alpha')], row
            assert shlex.split(path) == ['cd', 'path with spaces/'], row
            assert second == branch, row
            assert after[4:6] == ['wsh', 'wsh'], row
            expected_runs = '1' if variant.startswith('deferred-') or variant in ('vi', 'z-first') else '0'
            assert after[3] == expected_runs, row
            if variant == 'existing':
                assert before[2:] == after[2:], row
            if variant != 'vi':
                custom, _ = shell.capture(b'A\x18')
                assert custom == 'ACUSTOM', custom
                offset = len(shell.output)
                os.write(shell.fd, b'print -r -- DEFER_AUTO')
                shell.wait(b'SUGGEST_COMPLETE', offset)
                suggestion = shell.state()
                assert suggestion[0] == 'SUGGEST_COMPLETE', suggestion
                accepted, _ = shell.capture(b'\x05')
                assert accepted == 'print -r -- DEFER_AUTOSUGGEST_COMPLETE', accepted
                history, _ = shell.capture(b'print -r -- DEFER_AUTO\x1b[A')
                assert history == accepted, history
                os.write(shell.fd, b'nonexistent_deferred_command')
                time.sleep(.03)
                highlighted = shell.state()
                assert int(highlighted[1]) > 0, highlighted
                shell.capture(b'')
                row.update(custom=custom, suggestion=suggestion, accepted=accepted, history=history, highlighted=highlighted)
        finally:
            shell.close()
            (OUT / 'correctness.json').write_text(json.dumps(results, indent=2) + '\n')
    print('PASS: actual ZLE completion, editing composition, existing completion/custom Tab ownership, vi insert and z-first cases', flush=True)

def measure():
    rows = []
    host = {'before': Path('/proc/stat').read_text(), 'load_before': Path('/proc/loadavg').read_text()}
    try:
        for index in range(50):
            order = list(VARIANTS)
            if index % 2:
                order.reverse()
            for variant in order:
                if variant.endswith('-cold'):
                    (OUT / 'work' / variant / '.zcompdump').unlink(missing_ok=True)
                shell = Shell(variant, str(index) + '-' + variant)
                try:
                    branch, tab_ms = shell.complete('git switch wsh-native-')
                    expected = 'git switch wsh-native-' if variant == 'baseline' else 'git switch wsh-native-completion-unique'
                    assert branch.strip() == expected, branch
                    second, second_ms = shell.complete('git switch wsh-native-')
                    assert second == branch, second
                    rows.append({'round': index, 'variant': variant, 'startup_ms': shell.startup_ms, 'tab_ms': tab_ms, 'second_tab_ms': second_ms, 'buffer': branch})
                finally:
                    shell.close()
            if index % 10 == 9:
                print('Completed rounds:', index + 1, flush=True)
    finally:
        (OUT / 'samples.json').write_text(json.dumps(rows, indent=2) + '\n')
        host.update(after=Path('/proc/stat').read_text(), load_after=Path('/proc/loadavg').read_text())
        (OUT / 'host.json').write_text(json.dumps(host, indent=2) + '\n')
    summary = {}
    for variant in VARIANTS:
        values = [r for r in rows if r['variant'] == variant]
        summary[variant] = {'samples': len(values)}
        for metric in ('startup_ms', 'tab_ms', 'second_tab_ms'):
            data = sorted(r[metric] for r in values)
            for p in (50, 95):
                summary[variant][metric + '_p' + str(p)] = data[math.ceil(len(data) * p / 100) - 1]
    base = summary['baseline']['startup_ms_p95']
    gates = {}
    for variant in VARIANTS[1:]:
        budget = 100 if variant == 'eager-cold' else 20
        gates[variant] = {'startup': summary[variant]['startup_ms_p95'] - base <= budget, 'first_tab': summary[variant]['tab_ms_p95'] <= 100, 'second_tab': summary[variant]['second_tab_ms_p95'] <= 100}
    (OUT / 'summary.json').write_text(json.dumps({'results': summary, 'gates': gates}, indent=2) + '\n')
    print(json.dumps({'results': summary, 'gates': gates}, indent=2), flush=True)

if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['correctness']:
        prepare()
        correctness()
    elif sys.argv[1:] == ['measure']:
        measure()
    else:
        raise SystemExit('usage: run.py correctness|measure')
