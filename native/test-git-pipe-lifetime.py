#!/usr/bin/env python3
"""Real Git output plus an inherited-pipe fault must remain cancellable."""
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

RUNTIME = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve(); OUT.mkdir(parents=True, exist_ok=True)
require = '--require-bounded' in sys.argv[3:]
timeout_case = '--timeout' in sys.argv[3:]
repo = OUT / 'repo'; repo.mkdir()
for args in [['init', '-q', '-b', 'main'], ['config', 'user.name', 'pipe-test'], ['config', 'user.email', 'pipe@wsh.invalid']]:
    subprocess.run(['git', '-C', repo, *args], check=True)
(repo / 'file').write_text('seed\n')
subprocess.run(['git', '-C', repo, 'add', 'file'], check=True)
subprocess.run(['git', '-C', repo, 'commit', '-qm', 'seed'], check=True)
helper = OUT / 'bin'; helper.mkdir()
# Preserve real Git argv/parser/output. Only add a descendant holding stdout open.
(helper / 'git').write_text('''#!/bin/sh
/usr/bin/git "$@" || exit
sleep 30 &
printf '%s\\n' "$!" > "$WSH_FAULT_DIR/descendant.pid"
printf '%s\\n' "$$" > "$WSH_FAULT_DIR/group.pid"
exit 0
''')
(helper / 'git').chmod(0o755)
env = dict(os.environ, PATH=str(helper) + ':/usr/bin:/bin', WSH_FAULT_DIR=str(OUT))
trace = OUT / 'trace.jsonl'; env['WSH_TRACE_FILE'] = str(trace)
p = subprocess.Popen([RUNTIME, 'serve', '--theme', Path(__file__).resolve().parents[1] / 'themes/minimal.toml'], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
output = bytearray()
def receive(timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if select.select([p.stdout], [], [], min(.05, max(0, deadline - time.monotonic())))[0]:
            block = os.read(p.stdout.fileno(), 65536)
            if not block: break
            output.extend(block)
            if b'\n' in block: return

def send(value): p.stdin.write(json.dumps(value).encode() + b'\n'); p.stdin.flush()
try:
    receive(2); assert b'"type":"ready"' in output, bytes(output)
    send(dict(type='refresh', version=1, id=1, generation=1, cwd_hex=os.fsencode(repo).hex(), exit_status=0, duration_ms=None, privileged=False, reset_transient=False))
    deadline = time.monotonic() + 3
    while not (OUT / 'group.pid').exists():
        assert time.monotonic() < deadline
        time.sleep(.005)
    group = int((OUT / 'group.pid').read_text())
    # Wait until the direct command exits, leaving only its inherited stdout pipe.
    deadline = time.monotonic() + 1
    while Path('/proc/' + str(group)).exists():
        assert time.monotonic() < deadline
        time.sleep(.005)
    active_threads = len(list(Path('/proc/' + str(p.pid) + '/task').iterdir()))
    started = time.monotonic()
    if timeout_case:
        receive(2.5)
    else:
        send(dict(type='cancel', version=1, id=2, generation=1))
        receive(.5)
    send(dict(type='shutdown', version=1, id=3))
    try: p.wait(timeout=3)
    except subprocess.TimeoutExpired: p.kill(); p.wait()
    output.extend(p.stdout.read())
    stderr = p.stderr.read(); elapsed = time.monotonic() - started
    descendant = int((OUT / 'descendant.pid').read_text())
    deadline = time.monotonic() + .5
    while Path('/proc/' + str(descendant)).exists() and time.monotonic() < deadline:
        time.sleep(.005)
    descendant_gone = not Path('/proc/' + str(descendant)).exists()
    limit = 3 if timeout_case else 1
    passed = p.returncode == 0 and b'"type":"stopping"' in output and elapsed < limit and descendant_gone
    if timeout_case: passed = passed and b'"type":"error"' in output
    result = dict(status=p.returncode, mode='timeout' if timeout_case else 'cancel', active_threads=active_threads, cancellation_and_shutdown_seconds=elapsed, limit_seconds=limit, descendant_gone=descendant_gone, passed=passed, runtime_sha256=__import__('hashlib').sha256(RUNTIME.read_bytes()).hexdigest())
    (OUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    (OUT / 'stdout').write_bytes(output); (OUT / 'stderr').write_bytes(stderr)
    print(json.dumps(result, indent=2))
    if require: assert passed, (result, stderr)
finally:
    if p.poll() is None: p.kill(); p.wait()
    if (OUT / 'group.pid').exists():
        try: os.killpg(int((OUT / 'group.pid').read_text()), signal.SIGKILL)
        except ProcessLookupError: pass
