#!/usr/bin/env python3
"""Bound helper JSON round-trip cost without Git or editor work."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];binary=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve()
os.sched_setaffinity(0,{0})
env=dict(PATH='/usr/bin:/bin',HOME='/tmp',LC_ALL='C.UTF-8')
p=subprocess.Popen([binary,'serve','--theme',ROOT/'themes/minimal.toml'],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
rows=[]
try:
    assert json.loads(p.stdout.readline())['type']=='ready'
    for pair in range(1001):
        frame=json.dumps(dict(type='ping',version=1,id=pair),separators=(',',':')).encode()+b'\n'
        before=time.monotonic_ns();p.stdin.write(frame);p.stdin.flush();line=p.stdout.readline();elapsed=time.monotonic_ns()-before
        before=time.monotonic_ns();empty=time.monotonic_ns()-before
        assert json.loads(line)==dict(type='pong',version=1,id=pair)
        if pair:rows.append(dict(pair=pair,elapsed_ns=elapsed,empty_ns=empty))
    p.stdin.write(b'{"type":"shutdown","version":1,"id":0}\n');p.stdin.flush();assert json.loads(p.stdout.readline())['type']=='stopping'
    assert p.wait(timeout=3)==0 and not p.stderr.read()
finally:
    if p.poll() is None:p.kill();p.wait()
values=sorted(r['elapsed_ns'] for r in rows)
result=dict(samples=rows,summary=dict(median_ns=(values[499]+values[500])/2,p95_ns=values[949],empty_p95_ns=sorted(r['empty_ns'] for r in rows)[949]),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),cpu=0,trace_mode='off',command=sys.argv)
out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['summary'],indent=2))
