#!/usr/bin/env python3
"""Compare healthy bare startup before/after login recovery with one bundle."""
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BUNDLE = ROOT / 'bundles/ccf3c17708aae1b1fc23c4170d54ff6e78a919f0adc0e0950f3590c6325c9698'
MANAGERS = {'before': Path('/var/tmp/wsh-before-login-recovery'), 'after': ROOT / 'target/release/wsh'}
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

with tempfile.TemporaryDirectory(prefix='wsh-login-startup-') as directory:
    work = Path(directory)
    home = work / 'home'
    home.mkdir()
    (home / '.zshrc').write_text('WSH_THEME=""\nPROMPT="STARTUP> "\n')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('WSH_', 'WAKTERM_', 'ZSH_')) and k not in ('ZDOTDIR', 'XDG_DATA_HOME', 'BASH_ENV', 'ENV')}
    env.update(HOME=str(home), ZDOTDIR=str(home), WSH_STATE_ROOT=str(work / 'state'), WSH_THEME='', TERM='xterm-256color', LC_ALL='C.UTF-8')
    baseline = subprocess.run(['-wsh'], executable=str(MANAGERS['before']), env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
    assert baseline.returncode == 1 and b'no active bundle state' in baseline.stderr
    (OUT / 'baseline-login.json').write_text(json.dumps({'argv': ['-wsh'], 'status': baseline.returncode,
                                                       'stderr': baseline.stderr.decode()}, indent=2) + '\n')
    subprocess.run([str(MANAGERS['after']), 'bundle', 'activate', str(BUNDLE), '--state-root', str(work / 'state')], check=True, stdout=subprocess.PIPE)
    inputs = ['crates/wsh/src/main.rs', 'crates/wsh/src/login.rs', 'tests/login-shell.py', 'build/test-development-bundle.zsh', 'Cargo.lock']
    metadata = {'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
                'inputs': {name: sha(ROOT / name) for name in inputs}, 'managers': {k: sha(v) for k,v in MANAGERS.items()},
                'control_manager_source': '950bde517bdbb75d3c2a0933293b95f3d013a967',
                'bundle_sha256': sha(BUNDLE / 'manifest.json'), 'zsh_sha256': sha(BUNDLE / 'bin/zsh'),
                'runtime_sha256': sha(BUNDLE / 'bin/wsh-runtime'), 'harness_sha256': sha(Path(__file__)),
                'fixture_sha256': sha(home / '.zshrc'), 'config': (home / '.zshrc').read_text(),
                'host': subprocess.check_output(['uname', '-a']).decode().strip(), 'child_cpu': 0,
                'trace_mode': 'off', 'enabled_components': 'three editing defaults and directory jumping; existing prompt',
                'command': 'python3 benchmarks/login-recovery-2026-09-06/startup.py'}
    (OUT / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    with gzip.open(OUT / 'bundle-manifest.json.gz', 'wb') as output:
        output.write((BUNDLE / 'manifest.json').read_bytes())
    rows = []
    host = {'started': time.time(), 'stat_before': Path('/proc/stat').read_text(), 'load_before': Path('/proc/loadavg').read_text()}
    try:
        for index in range(50):
            for variant in (['before', 'after'] if index % 2 == 0 else ['after', 'before']):
                started = time.monotonic_ns()
                pid, fd = pty.fork()
                if pid == 0:
                    os.chdir(home)
                    os.sched_setaffinity(0, {0})
                    os.execve(str(MANAGERS[variant]), ['wsh'], env)
                output = bytearray()
                try:
                    deadline = time.monotonic() + 8
                    while b'\x1b]133;B\x1b\\' not in output:
                        assert time.monotonic() < deadline, bytes(output)
                        if select.select([fd], [], [], .1)[0]:
                            output.extend(os.read(fd, 65536))
                    elapsed = (time.monotonic_ns() - started) / 1e6
                    assert os.readlink('/proc/' + str(pid) + '/exe') == str(BUNDLE / 'bin/zsh')
                    rows.append({'round': index, 'variant': variant, 'startup_ms': elapsed, 'same_pid_exec': True})
                finally:
                    os.kill(pid, signal.SIGHUP)
                    os.waitpid(pid, 0)
                    os.close(fd)
    finally:
        (OUT / 'samples.json').write_text(json.dumps(rows, indent=2) + '\n')
        host.update(ended=time.time(), stat_after=Path('/proc/stat').read_text(), load_after=Path('/proc/loadavg').read_text())
        (OUT / 'host.json').write_text(json.dumps(host, indent=2) + '\n')
    def p(values, percentile):
        return sorted(values)[math.ceil(len(values)*percentile/100)-1]
    pairs = [{r['variant']: r['startup_ms'] for r in rows if r['round'] == index} for index in range(50)]
    overhead = [pair['after'] - pair['before'] for pair in pairs]
    summary = {'pairs': 50, 'paired_overhead_p95_ms': p(overhead, 95), 'gate_pass': p(overhead, 95) <= 3,
               'variants': {v: {str(q): p([r['startup_ms'] for r in rows if r['variant'] == v], q) for q in (50,95)} for v in MANAGERS}}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
