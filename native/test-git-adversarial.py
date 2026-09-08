#!/usr/bin/env python3
"""Bound malformed local metadata and repeated cancellation in the real runtime."""
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve(); OUT.mkdir(parents=True)
base = OUT / 'base'; base.mkdir()
env = dict(os.environ, HOME=str(OUT), GIT_CONFIG_NOSYSTEM='1', LC_ALL='C.UTF-8')
for args in [('init', '-q', '-b', 'main'), ('config', 'user.name', 'adversarial'), ('config', 'user.email', 'adversarial@wsh.invalid')]:
    subprocess.run(['git', '-C', base, *args], env=env, check=True)
(base / 'file').write_text('seed\n')
subprocess.run(['git', '-C', base, 'add', 'file'], env=env, check=True)
subprocess.run(['git', '-C', base, 'commit', '-qm', 'seed'], env=env, check=True)

class Runtime:
    def __init__(self, environment):
        self.p = subprocess.Popen([RUNTIME, 'serve', '--theme', ROOT / 'themes/minimal.toml'], env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.buffer = bytearray()
        assert self.read()['type'] == 'ready'
    def send(self, kind, id, **fields):
        self.p.stdin.write(json.dumps(dict(type=kind, version=1, id=id, **fields)).encode() + b'\n'); self.p.stdin.flush()
    def refresh(self, repo, generation):
        self.send('refresh', generation, generation=generation, cwd_hex=os.fsencode(repo).hex(), exit_status=0, duration_ms=None, privileged=False, reset_transient=False)
    def read(self):
        deadline = time.monotonic() + 3
        while b'\n' not in self.buffer:
            assert time.monotonic() < deadline, bytes(self.buffer)
            if select.select([self.p.stdout], [], [], .05)[0]:
                block = os.read(self.p.stdout.fileno(), 65536)
                assert block, (self.p.poll(), self.p.stderr.read())
                self.buffer.extend(block)
        line, _, rest = self.buffer.partition(b'\n'); self.buffer[:] = rest
        return json.loads(line)
    def close(self):
        self.send('shutdown', 1000)
        while self.read()['type'] != 'stopping': pass
        assert self.p.wait(timeout=3) == 0, self.p.stderr.read()
    def kill(self):
        if self.p.poll() is None: self.p.kill(); self.p.wait()

results = []
def persist(): (OUT / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
for name, path, value, expected in [
    ('missing-head', 'HEAD', None, 'absent'),
    ('invalid-utf8-head', 'HEAD', b'\xff', 'absent'),
    ('nul-head', 'HEAD', b'ref: refs/heads/main\0ignored', 'absent'),
    ('oversized-head', 'HEAD', b'x' * 65536, 'absent'),
    ('fifo-head', 'HEAD', 'fifo', 'absent'),
    ('fifo-tag', 'refs/tags/fifo', 'fifo', 'snapshot'),
    ('fifo-packed-refs', 'packed-refs', 'fifo', 'bounded'),
    ('oversized-packed-record', 'packed-refs', b'x' * 65537 + b'\n', 'bounded'),
    ('cyclic-tag-directory', 'refs/tags/cycle', 'cycle', 'snapshot'),
]:
    repo = OUT / name; shutil.copytree(base, repo)
    target = repo / '.git' / path; target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    if value == 'fifo': os.mkfifo(target)
    elif value == 'cycle': target.symlink_to(target.parent, target_is_directory=True)
    elif value is not None: target.write_bytes(value)
    runtime = Runtime(env)
    try:
        started = time.monotonic(); runtime.refresh(repo, 1); response = runtime.read(); elapsed = time.monotonic() - started
        assert elapsed < 3
        if expected == 'absent': assert response['type'] == 'snapshot' and not response['snapshot']['found'], response
        if expected == 'snapshot': assert response['type'] == 'snapshot' and response['snapshot']['found'], response
        runtime.send('ping', 2); assert runtime.read()['type'] == 'pong'
        runtime.close()
        results.append(dict(case=name, response=response, elapsed_seconds=elapsed, passed=True)); persist()
    finally: runtime.kill()

helper = OUT / 'bin'; helper.mkdir()
(helper / 'git').write_text('#!/bin/sh\n[ "$GIT_OPTIONAL_LOCKS" = 0 ] || exit 99\nprintf "%s\\n" "$$" >> "$WSH_GIT_PID_FILE"\n/usr/bin/git "$@" || exit\nexec /usr/bin/sleep .03\n')
(helper / 'git').chmod(0o755)
pids = OUT / 'pids'
runtime = Runtime(dict(env, PATH=str(helper) + ':/usr/bin:/bin', WSH_GIT_PID_FILE=str(pids)))
messages = []
try:
    for generation in range(1, 51):
        runtime.refresh(base, generation)
        time.sleep(.003)
        runtime.send('cancel', 100 + generation, generation=generation)
        while True:
            response = runtime.read(); messages.append(response)
            if response['id'] == 100 + generation: break
        assert response['type'] == 'cancelled', response
    runtime.refresh(base, 51)
    while True:
        response = runtime.read(); messages.append(response)
        if response['type'] == 'snapshot' and response['generation'] == 51: break
        assert response['type'] != 'snapshot', response
    runtime.close()
    deadline = time.monotonic() + 1
    launched = [int(p) for p in pids.read_text().splitlines()]
    while any(Path(f'/proc/{p}').exists() for p in launched) and time.monotonic() < deadline: time.sleep(.005)
    assert all(not Path(f'/proc/{p}').exists() for p in launched)
    results.append(dict(case='50-cancellations-and-final-generation', passed=True, launched_pids=launched, messages=messages)); persist()
finally: runtime.kill()
(OUT / 'metadata.json').write_text(json.dumps(dict(runtime_sha256=hashlib.sha256(RUNTIME.read_bytes()).hexdigest(), command='python3 native/test-git-adversarial.py ' + ' '.join(sys.argv[1:])), indent=2) + '\n')
print('PASS: nine malformed metadata cases and 50 cancellations followed by a complete final snapshot')
