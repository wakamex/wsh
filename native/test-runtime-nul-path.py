#!/usr/bin/env python3
"""Retain the deliberate rejection of an impossible filesystem path."""
import json
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
results={}
for name,binary in zip(['rust','c'],sys.argv[1:3]):
    p=subprocess.Popen([binary,'serve','--theme',root/'themes/minimal.toml'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        assert json.loads(p.stdout.readline())['type']=='ready'
        request=dict(type='refresh',version=1,id=1,generation=1,cwd_hex=b'/tmp/a\0b'.hex(),exit_status=0,duration_ms=None,privileged=False,reset_transient=False)
        p.stdin.write(json.dumps(request).encode()+b'\n');p.stdin.flush();results[name]=json.loads(p.stdout.readline())
        p.stdin.write(b'{"type":"shutdown","version":1,"id":2}\n');p.stdin.flush();assert json.loads(p.stdout.readline())['type']=='stopping'
        assert p.wait(timeout=3)==0 and not p.stderr.read()
    finally:
        if p.poll() is None:p.kill();p.wait()
assert results['rust']['type']=='snapshot' and not results['rust']['snapshot']['found']
assert results['c']==dict(version=1,type='error',id=1,error='cwd contains a NUL byte')
Path(sys.argv[3]).write_text(json.dumps(dict(input=request,observed=results,expected_difference=True),indent=2)+'\n')
print('PASS: retained explicit NUL-path rejection difference')
