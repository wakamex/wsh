#!/usr/bin/env python3
"""Paired process-cold and warm helper collection, with complete snapshot parity."""
import hashlib
import json
import os
from pathlib import Path
import resource
import select
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BINARIES = dict(control=Path(sys.argv[1]).resolve(), candidate=Path(sys.argv[2]).resolve())
OUT = Path(sys.argv[3]).resolve(); OUT.mkdir(parents=True, exist_ok=True)
repo = OUT / 'repository'; repo.mkdir()
home = OUT / 'home'; home.mkdir()
env = dict(HOME=str(home), PATH='/usr/bin:/bin', LC_ALL='C.UTF-8', TZ='UTC', GIT_CONFIG_NOSYSTEM='1')
def git(*args): subprocess.run(['git', '-C', repo, *args], check=True, env=env, capture_output=True)
git('init', '-q', '-b', 'main'); git('config', 'user.name', 'collector'); git('config', 'user.email', 'collector@wsh.invalid')
for i in range(1000): (repo / f'file-{i}').write_text('seed\n')
git('add', '.'); git('commit', '-qm', 'seed')

class Runtime:
    def __init__(self, variant):
        self.before_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
        self.p = subprocess.Popen([BINARIES[variant], 'serve', '--theme', ROOT / 'themes/minimal.toml'], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=lambda: os.sched_setaffinity(0, {0}))
        self.buffer = bytearray(); self.generation = 0
        assert self.read()['type'] == 'ready'
    def read(self):
        deadline = time.monotonic() + 5
        while b'\n' not in self.buffer:
            assert time.monotonic() < deadline, bytes(self.buffer)
            if select.select([self.p.stdout], [], [], .05)[0]:
                block = os.read(self.p.stdout.fileno(), 65536)
                assert block, self.p.stderr.read()
                self.buffer.extend(block)
        line, _, rest = self.buffer.partition(b'\n'); self.buffer = bytearray(rest)
        return json.loads(line)
    def send(self, value): self.p.stdin.write(json.dumps(value).encode() + b'\n'); self.p.stdin.flush()
    def collect(self):
        self.generation += 1
        request = dict(type='refresh', version=1, id=self.generation, generation=self.generation, cwd_hex=os.fsencode(repo).hex(), exit_status=0, duration_ms=None, privileged=False, reset_transient=False)
        start = time.monotonic_ns(); self.send(request); response = self.read(); elapsed = (time.monotonic_ns() - start) / 1e6
        assert response['type'] == 'snapshot' and response['generation'] == self.generation, response
        return elapsed, response['snapshot']
    def stop(self):
        self.send(dict(type='shutdown', version=1, id=self.generation + 1)); assert self.read()['type'] == 'stopping'
        assert self.p.wait(timeout=3) == 0
        cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
        return (cpu.ru_utime + cpu.ru_stime - self.before_cpu.ru_utime - self.before_cpu.ru_stime) * 1000

rows = []
for state in ['clean', 'dirty', 'untracked']:
    git('reset', '--hard', '-q', 'HEAD'); git('clean', '-fdq')
    if state == 'dirty':
        for i in range(100): (repo / f'file-{i}').write_text('changed\n')
    if state == 'untracked':
        for i in range(100): (repo / f'untracked-{i}').write_text('new\n')
    for mode in ['process-cold', 'warm']:
        warm = {v: Runtime(v) for v in BINARIES} if mode == 'warm' else {}
        if warm:
            for runtime in warm.values(): runtime.collect()
        try:
            for pair in range(50):
                snapshots = {}
                for variant in (['control', 'candidate'] if pair % 2 == 0 else ['candidate', 'control']):
                    runtime = warm.get(variant) or Runtime(variant)
                    try:
                        elapsed, snapshot = runtime.collect(); snapshots[variant] = snapshot
                    finally:
                        if not warm: cpu_ms = runtime.stop()
                    row = dict(state=state, mode=mode, pair=pair, variant=variant, collection_ms=elapsed)
                    if not warm: row['helper_and_git_cpu_ms'] = cpu_ms
                    rows.append(row)
                assert snapshots['control'] == snapshots['candidate'], snapshots
        finally:
            for runtime in warm.values(): runtime.stop()
summary = {}
for state in ['clean', 'dirty', 'untracked']:
    for mode in ['process-cold', 'warm']:
        selected = [r for r in rows if r['state'] == state and r['mode'] == mode]
        values = {v: [r['collection_ms'] for r in selected if r['variant'] == v] for v in BINARIES}
        differences = sorted(a - b for a, b in zip(values['candidate'], values['control']))
        summary[state + '/' + mode] = dict(pairs=50, control_median_ms=sorted(values['control'])[24], candidate_median_ms=sorted(values['candidate'])[24], paired_p95_ms=differences[47], limit_ms=3, passed=differences[47] <= 3)
meta = dict(command='python3 native/measure-git.py ' + ' '.join(sys.argv[1:]), source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() + '+dirty', binaries={v:dict(path=str(b), sha256=hashlib.sha256(b.read_bytes()).hexdigest()) for v, b in BINARIES.items()}, cpu=0, trace_mode='off', files=1000, changed_files=100, cold_definition='fresh helper after ready handshake; filesystem cache not forcibly evicted', environment=env)
for name, value in [('samples', rows), ('summary', summary), ('metadata', meta)]: (OUT / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
print(json.dumps(summary, indent=2))
assert all(r['passed'] for r in summary.values())
