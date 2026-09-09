#!/usr/bin/env python3
"""Compare the C protocol decoder with the actual Rust runtime."""
import hashlib
import json
import os
from pathlib import Path
import random
import select
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BINARIES = {name: Path(path).resolve() for name, path in zip(['rust', 'c'], sys.argv[1:3])}
OUT = Path(sys.argv[3]).resolve(); OUT.mkdir(parents=True)
ENV = dict(os.environ, HOME=str(OUT), USER='protocol', HOST='host', LC_ALL='C.UTF-8')
ENV.pop('WSH_TRACE_FILE', None); ENV.pop('WSH_PROFILE_STARTED_UNIX_US', None)
class Runtime:
    def __init__(self, binary, theme='minimal'):
        self.p = subprocess.Popen([binary, 'serve', '--theme', ROOT / f'themes/{theme}.toml'], env=ENV, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.buffer = bytearray(); assert self.read()['type'] == 'ready'
    def read(self):
        until = time.monotonic() + 4
        while b'\n' not in self.buffer:
            assert time.monotonic() < until, bytes(self.buffer)
            if select.select([self.p.stdout], [], [], .05)[0]:
                data = os.read(self.p.stdout.fileno(), 65536)
                assert data, (self.p.poll(), self.p.stderr.read())
                self.buffer.extend(data)
        line, _, rest = self.buffer.partition(b'\n'); self.buffer[:] = rest
        return json.loads(line)
    def send(self, line): self.p.stdin.write(line + b'\n'); self.p.stdin.flush()
    def close(self):
        self.send(b'{"type":"shutdown","version":1,"id":0}'); assert self.read()['type'] == 'stopping'
        assert self.p.wait(timeout=3) == 0
        assert not self.p.stderr.read()
    def kill(self):
        if self.p.poll() is None: self.p.kill(); self.p.wait()

def encoded(value): return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
base = dict(type='ping', version=1, id=7)
cases = [('ordinary', encoded(base))]
for key in ['type', 'version', 'id']:
    copy = dict(base); del copy[key]; cases.append(('missing-' + key, encoded(copy)))
    cases.append(('duplicate-' + key, encoded(base)[:-1] + b',' + encoded(key) + b':' + encoded(base[key]) + b'}'))
    for value in [None, True, False, [], {}, '', '1', -1, 0, 1, 1.0, 2**32, 2**64-1, 2**64, '\x00']:
        copy = dict(base); copy[key] = value; cases.append((f'{key}-{value!r}', encoded(copy)))
for extra in ['unknown', 'type\0', '\0type']:
    cases.append(('unknown-' + repr(extra), encoded(dict(base, **{extra: 1}))))
for raw in [b'', b'null', b'[]', b'{}', b'1', b'false', b'{', b'\xff', b'\xef\xbb\xbf'+encoded(base), encoded(base)+b' {}', b' '+encoded(base)+b'\r', b'{"type":"ping","version":1,"id":-0}', b'{"type":"ping","version":1,"id":1e0}']:
    cases.append(('raw-' + raw.hex(), raw))
refresh = dict(type='refresh', version=1, id=3, generation=1, cwd_hex=os.fsencode(OUT).hex(), exit_status=0, duration_ms=None, privileged=False, reset_transient=False)
for kind, template in [('refresh', refresh), ('cancel', dict(type='cancel', version=1, id=4, generation=0))]:
    for key in template:
        copy = dict(template); del copy[key]; cases.append((f'{kind}-missing-{key}', encoded(copy)))
        cases.append((f'{kind}-duplicate-{key}', encoded(template)[:-1]+b','+encoded(key)+b':'+encoded(template[key])+b'}'))
        for value in [None, True, [], {}, '', -1, 0, 1.0, 2**32, 2**64-1, 2**64]:
            copy = dict(template); copy[key] = value; cases.append((f'{kind}-{key}-{value!r}', encoded(copy)))
rng = random.Random(20260909)
for i in range(2000):
    value = bytearray(encoded(base))
    for _ in range(rng.randrange(1, 5)):
        index = rng.randrange(len(value)); byte = rng.randrange(256)
        value[index] = 32 if byte in (10, 13) else byte
    cases.append((f'mutation-{i}', bytes(value)))
results = []
runtimes = {name: Runtime(binary) for name, binary in BINARIES.items()}
try:
    for name, frame in cases:
        observed = {}
        for variant, runtime in runtimes.items(): runtime.send(frame); observed[variant] = runtime.read()
        passed = observed['rust'] == observed['c']
        results.append(dict(case=name, input_hex=frame.hex(), observed=observed, passed=passed))
        if not passed: raise AssertionError(results[-1])
    for runtime in runtimes.values(): runtime.close()
finally:
    (OUT / 'decoder.json').write_text(json.dumps(results, indent=2) + '\n')
    for runtime in runtimes.values(): runtime.kill()

results = []
for theme in ['minimal', 'wakamex', 'robbyrussell', 'agnoster']:
    runtimes = {name: Runtime(binary, theme) for name, binary in BINARIES.items()}
    try:
        for generation in range(1, 101):
            request = dict(type='refresh', version=1, id=2**64-generation, generation=generation, cwd_hex=os.fsencode(OUT).hex(), exit_status=[-2**31, 0, 2**31-1][generation%3], privileged=generation%2==0, reset_transient=generation%3==0)
            if generation%4: request['duration_ms'] = [None, 0, 2**64-1][generation%3]
            observed = {}
            for variant, runtime in runtimes.items(): runtime.send(encoded(request)); observed[variant] = runtime.read()
            assert observed['rust']['type'] == 'snapshot'
            passed = observed['rust'] == observed['c']; results.append(dict(theme=theme, generation=generation, observed=observed, passed=passed)); assert passed, results[-1]
        stale = dict(request, id=0)
        for runtime in runtimes.values():
            runtime.send(encoded(stale)); assert runtime.read() == dict(version=1,type='error',id=0,error='refresh generation is stale')
            runtime.close()
    finally:
        (OUT / 'snapshots.json').write_text(json.dumps(results, indent=2) + '\n')
        for runtime in runtimes.values(): runtime.kill()
(OUT / 'metadata.json').write_text(json.dumps(dict(binaries={n:dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in BINARIES.items()}, command=sys.argv), indent=2)+'\n')
print(f'PASS: {len(cases)} decoder cases and 400 complete prompt/snapshot comparisons')
