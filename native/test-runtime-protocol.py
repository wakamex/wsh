#!/usr/bin/env python3
"""Exercise the installed JSON protocol and its integer boundaries on a real helper."""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True)
MAXIMUM = 2**63-1
results = []
p = subprocess.Popen([BINARY, 'serve', '--theme', ROOT/'themes/minimal.toml'],
    env=dict(os.environ, HOME=str(OUT), LC_ALL='C.UTF-8'),
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
buffer = bytearray()
def read():
    deadline = time.monotonic()+4
    while b'\n' not in buffer:
        assert time.monotonic() < deadline, bytes(buffer)
        if select.select([p.stdout], [], [], .05)[0]:
            data = os.read(p.stdout.fileno(), 65536)
            assert data, (p.poll(), p.stderr.read())
            buffer.extend(data)
    line, _, rest = buffer.partition(b'\n')
    buffer[:] = rest
    return json.loads(line)
def exchange(name, request, expected):
    frame = request if isinstance(request, bytes) else json.dumps(request, separators=(',', ':')).encode()
    p.stdin.write(frame+b'\n')
    p.stdin.flush()
    observed = read()
    results.append(dict(case=name, input_hex=frame.hex(), observed=observed))
    assert observed == expected, (name, observed, expected)
def error(id=None, text='malformed request'):
    return dict(version=1, type='error', id=id, error=text)
try:
    assert read()['type'] == 'ready'
    ping = dict(type='ping', version=1, id=7)
    for value in [0, 1, MAXIMUM]:
        exchange('id-'+str(value), dict(ping,id=value), dict(version=1,type='pong',id=value))
    exchange('negative-zero', b'{"type":"ping","version":1,"id":-0}', dict(version=1,type='pong',id=0))
    for key in ['id','version']:
        values = [None, True, False, [], {}, '', '1', -1, 1.0, MAXIMUM+1, 2**64-1, 2**64]
        if key == 'version': values += [2**32]
        for value in values:
            exchange(key+'-'+repr(value),dict(ping,**{key:value}),error())
    exchange('unsupported-version',dict(ping,version=2),error(7,'unsupported protocol version'))
    refresh = dict(type='refresh', version=1, id=3, generation=1, cwd_hex=os.fsencode(OUT).hex(),
                   exit_status=0, duration_ms=None, privileged=False, reset_transient=False)
    for template in [ping, refresh, dict(type='cancel',version=1,id=4,generation=0)]:
        for key in template:
            if key != 'duration_ms':
                missing = dict(template)
                del missing[key]
                exchange(template['type']+'-missing-'+key,missing,error())
            frame = json.dumps(template,separators=(',',':')).encode()[:-1]
            frame += b','+json.dumps(key).encode()+b':'+json.dumps(template[key]).encode()+b'}'
            exchange(template['type']+'-duplicate-'+key,frame,error())
        exchange(template['type']+'-unknown',dict(template,unknown=1),error())
    for key in ['generation','duration_ms']:
        for value in [-1, 1.0, True, MAXIMUM+1, 2**64-1]:
            exchange(key+'-'+repr(value),dict(refresh,**{key:value}),error())
    for value in [-2**31-1,2**31,True,1.0]:
        exchange('status-'+repr(value),dict(refresh,exit_status=value),error())
    for raw in [b'',b'null',b'[]',b'{}',b'false',b'{',b'\xff',
                b'{"type":"ping","version":1,"id":1} {}',
                b'{"type":"ping","version":1,"id":1e0}',
                b'{"type":"ping","version":1,"id":1,"type\\u0000":0}']:
        exchange('raw-'+raw.hex(),raw,error())
    exchange('nul-path',dict(refresh,cwd_hex=b'/tmp/a\0b'.hex()),error(3,'cwd contains a NUL byte'))
    # Invalid requests must not advance the current generation.
    for generation in [1,MAXIMUM]:
        request=dict(refresh,id=MAXIMUM,generation=generation,duration_ms=MAXIMUM,exit_status=-2**31)
        p.stdin.write(json.dumps(request).encode()+b'\n')
        p.stdin.flush()
        observed=read()
        assert observed['type']=='snapshot' and observed['id']==MAXIMUM and observed['generation']==generation, observed
        results.append(dict(case='maximum-snapshot-'+str(generation),observed=observed))
    exchange('stale-generation',dict(refresh,id=8),error(8,'refresh generation is stale'))
    exchange('maximum-cancel',dict(type='cancel',version=1,id=MAXIMUM,generation=MAXIMUM),
             dict(version=1,type='cancelled',id=MAXIMUM))
    exchange('recovery-ping',ping,dict(version=1,type='pong',id=7))
    exchange('shutdown',dict(type='shutdown',version=1,id=MAXIMUM),dict(version=1,type='stopping',id=MAXIMUM))
    assert p.wait(timeout=3)==0 and not p.stderr.read()
finally:
    if p.poll() is None:
        p.kill()
        p.wait()
    (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
print(f'PASS: {len(results)} real-helper protocol, integer, path and recovery boundaries')
