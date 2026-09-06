#!/usr/bin/env python3
"""Screen native compinit with actual ZLE; keep every observation."""
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

OUT = Path(__file__).resolve().parent
ROOT = Path('/code/wsh')
BUNDLE = ROOT / 'bundles/ccf3c17708aae1b1fc23c4170d54ff6e78a919f0adc0e0950f3590c6325c9698'
MANAGER = ROOT / 'target/release/wsh'
READY = b'\x1b]133;B\x1b\\'
CAPTURE = b'\x1eBUFFER:'
CONFIG = r'''
PROMPT='COMP> '
HISTFILE=$HOME/history
SAVEHIST=0
ZSHZ_DATA=$HOME/jump-data
if [[ $COMP_CASE != baseline ]]; then
  autoload -Uz compinit
  compinit -i -d "$HOME/.zcompdump"
fi
_capture() {
  print -nr -- $'\x1eBUFFER:'"$BUFFER"$'\x1f'
  BUFFER=''
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
        offset = len(self.output)
        started = time.monotonic_ns()
        os.write(self.fd, text.encode() + b'\t\x07')
        self.wait(b'\x1f', offset)
        elapsed = (time.monotonic_ns() - started) / 1e6
        start = self.output.index(CAPTURE, offset) + len(CAPTURE)
        end = self.output.index(b'\x1f', start)
        return self.output[start:end].decode(), elapsed

    def close(self):
        os.kill(self.pid, signal.SIGHUP)
        os.waitpid(self.pid, 0)
        os.close(self.fd)
        with gzip.open(OUT / 'transcripts' / (self.label + '.gz'), 'wb') as stream:
            stream.write(self.output)

def prepare():
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
    for variant in ('baseline', 'cold', 'warm'):
        home = work / variant
        home.mkdir(mode=0o700)
        (home / '.zshrc').write_text(CONFIG)
        (home / 'jump-data').write_text(str(fixture / 'project alpha') + '|10|' + str(int(time.time())) + '\n')
    manifest = json.loads((BUNDLE / 'manifest.json').read_text())
    metadata = {'manager_source': run('git', '-C', ROOT, 'rev-parse', 'HEAD').decode().strip(), 'manager_sha256': sha(MANAGER), 'bundle_path': str(BUNDLE), 'bundle_sha256': sha(BUNDLE / 'manifest.json'), 'zsh_sha256': sha(BUNDLE / 'bin/zsh'), 'runtime_sha256': sha(BUNDLE / 'bin/wsh-runtime'), 'trace_mode': 'off', 'theme': '', 'editing_defaults': 'all enabled', 'host': run('uname', '-a').decode().strip(), 'cpu': 0, 'command': 'python3 ' + str(OUT / 'run.py'), 'config_sha256': hashlib.sha256(CONFIG.encode()).hexdigest(), 'harness_sha256': sha(Path(__file__)), 'plan_sha256': sha(OUT / 'plan.md'), 'git_version': run('git', '--version').decode().strip()}
    (OUT / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    with gzip.open(OUT / 'bundle-manifest.json.gz', 'wb') as stream:
        stream.write(json.dumps(manifest, indent=2).encode())

def correctness():
    results = []
    for variant in ('baseline', 'cold', 'warm'):
        shell = Shell(variant, 'correctness-' + variant)
        try:
            branch, _ = shell.complete('git switch wsh-native-')
            jump, _ = shell.complete('z alpha')
            path, _ = shell.complete('cd path')
            row = {'variant': variant, 'branch': branch, 'jump': jump, 'path': path}
            results.append(row)
            if variant == 'baseline':
                assert branch.strip() == 'git switch wsh-native-', row
                assert jump.strip() == 'z alpha', row
            else:
                assert shlex.split(branch) == ['git', 'switch', 'wsh-native-completion-unique'], row
                assert shlex.split(jump) == ['z', str(OUT / 'work/fixture/project alpha')], row
            assert shlex.split(path) == ['cd', 'path with spaces/'], row
        finally:
            shell.close()
            (OUT / 'correctness.json').write_text(json.dumps(results, indent=2) + '\n')
    print('PASS: baseline reproduces missing command completion; native compinit completes Git, z, and spaced paths', flush=True)

def measure():
    rows = []
    host = {'before': Path('/proc/stat').read_text(), 'load_before': Path('/proc/loadavg').read_text()}
    try:
        for index in range(50):
            order = ['baseline', 'cold', 'warm']
            if index % 2:
                order.reverse()
            for variant in order:
                if variant == 'cold':
                    (OUT / 'work/cold/.zcompdump').unlink(missing_ok=True)
                shell = Shell(variant, str(index) + '-' + variant)
                try:
                    branch, tab_ms = shell.complete('git switch wsh-native-')
                    expected = 'git switch wsh-native-' if variant == 'baseline' else 'git switch wsh-native-completion-unique'
                    assert branch.strip() == expected, branch
                    rows.append({'round': index, 'variant': variant, 'startup_ms': shell.startup_ms, 'tab_ms': tab_ms, 'buffer': branch})
                finally:
                    shell.close()
            if index % 10 == 9:
                print('Completed rounds:', index + 1, flush=True)
    finally:
        (OUT / 'samples.json').write_text(json.dumps(rows, indent=2) + '\n')
        host.update(after=Path('/proc/stat').read_text(), load_after=Path('/proc/loadavg').read_text())
        (OUT / 'host.json').write_text(json.dumps(host, indent=2) + '\n')
    summary = {}
    for variant in ('baseline', 'cold', 'warm'):
        values = [r for r in rows if r['variant'] == variant]
        summary[variant] = {'samples': len(values)}
        for metric in ('startup_ms', 'tab_ms'):
            data = sorted(r[metric] for r in values)
            for p in (50, 95):
                summary[variant][metric + '_p' + str(p)] = data[math.ceil(len(data) * p / 100) - 1]
    base = summary['baseline']['startup_ms_p95']
    gates = {'warm_startup': summary['warm']['startup_ms_p95'] - base <= 20, 'cold_startup': summary['cold']['startup_ms_p95'] - base <= 100, 'first_tab': max(summary[v]['tab_ms_p95'] for v in ('cold', 'warm')) <= 100}
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
