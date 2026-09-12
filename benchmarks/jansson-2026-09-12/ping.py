#!/usr/bin/env python3
"""Alternate real helper ping round trips on one CPU, outside Git/editor work."""
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
binaries = dict(zip(('control', 'candidate'), map(Path, sys.argv[1:3])))
output = Path(sys.argv[3])
os.sched_setaffinity(0, {0})
env = dict(PATH='/usr/bin:/bin', HOME=str(output.parent), LC_ALL='C.UTF-8')
processes = {name: subprocess.Popen([binary, 'serve', '--theme', ROOT/'themes/minimal.toml'],
             env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
             for name, binary in binaries.items()}
rows = []
try:
    for p in processes.values():
        assert json.loads(p.stdout.readline())['type'] == 'ready'
    for pair in range(1050):
        frame = json.dumps(dict(type='ping', version=1, id=pair), separators=(',', ':')).encode()+b'\n'
        for variant in (('control', 'candidate') if pair % 2 == 0 else ('candidate', 'control')):
            p = processes[variant]
            started = time.monotonic_ns()
            p.stdin.write(frame)
            p.stdin.flush()
            reply = p.stdout.readline()
            elapsed = time.monotonic_ns()-started
            assert json.loads(reply) == dict(type='pong', version=1, id=pair)
            if pair >= 50:
                rows.append(dict(pair=pair-50, variant=variant, elapsed_ns=elapsed))
    for p in processes.values():
        p.stdin.write(b'{"type":"shutdown","version":1,"id":0}\n')
        p.stdin.flush()
        assert json.loads(p.stdout.readline())['type'] == 'stopping'
        assert p.wait(timeout=3) == 0 and not p.stderr.read()
finally:
    for p in processes.values():
        if p.poll() is None:
            p.kill()
            p.wait()
values = {v: [r['elapsed_ns'] for r in rows if r['variant'] == v] for v in binaries}
differences = sorted(c-b for b, c in zip(values['control'], values['candidate']))
summary = dict(pairs=1000, median_ns={v:statistics.median(x) for v,x in values.items()},
               paired_p95_delta_ns=differences[949])
output.write_text(json.dumps(dict(samples=rows,summary=summary,cpu=0,trace_mode='off',
    command=sys.argv,binaries={v:hashlib.sha256(p.read_bytes()).hexdigest() for v,p in binaries.items()}),indent=2)+'\n')
print(json.dumps(summary,indent=2))
