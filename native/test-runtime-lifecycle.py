#!/usr/bin/env python3
"""Real helper lifecycle, bounded input, trace recovery and process cleanup."""
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(sys.argv[1]).resolve(); OUT = Path(sys.argv[2]).resolve(); OUT.mkdir(parents=True)
ENV = dict(os.environ, HOME=str(OUT), PATH='/usr/bin:/bin', LC_ALL='C.UTF-8')
ENV.pop('WSH_TRACE_FILE', None); ENV.pop('WSH_PROFILE_STARTED_UNIX_US', None)
repo = OUT/'repo'; repo.mkdir()
subprocess.run(['git','init','-qb','main',repo],check=True)
refresh = dict(type='refresh',version=1,id=1,generation=1,cwd_hex=os.fsencode(repo).hex(),exit_status=0,duration_ms=None,privileged=False,reset_transient=False)
args = [str(BINARY),'serve','--theme',str(ROOT/'themes/minimal.toml')]
results=[]
def persist(): (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
def frame(value):return json.dumps(value,separators=(',',':')).encode()+b'\n'
class Runtime:
    def __init__(self, env=ENV):
        self.p=subprocess.Popen(args,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);self.buffer=bytearray();assert self.read()['type']=='ready'
    def read(self,timeout=4):
        deadline=time.monotonic()+timeout
        while b'\n' not in self.buffer:
            assert time.monotonic()<deadline, bytes(self.buffer)
            if select.select([self.p.stdout],[],[],.02)[0]:
                data=os.read(self.p.stdout.fileno(),65536);assert data,(self.p.poll(),self.p.stderr.read());self.buffer.extend(data)
        line,_,rest=self.buffer.partition(b'\n');self.buffer[:]=rest;return json.loads(line)
    def raw(self,value):self.p.stdin.write(value);self.p.stdin.flush()
    def send(self,value):self.raw(frame(value))
    def close(self):
        self.send(dict(type='shutdown',version=1,id=9));assert self.read()['type']=='stopping';self.wait()
    def wait(self,status=0):
        assert self.p.wait(timeout=3)==status
        error=self.p.stderr.read();assert b'Sanitizer' not in error and b'runtime error:' not in error,error
        if not status:assert not error,error
        return error.decode()
    def kill(self):
        if self.p.poll() is None:self.p.kill();self.p.wait()

for mode in ['partial-during-worker','eof','partial-eof','empty-line','exact-line-bound','oversized-line']:
    runtime=Runtime()
    try:
        if mode=='partial-during-worker':
            runtime.send(refresh);runtime.raw(b'{"type":"pi');assert runtime.read()['type']=='snapshot'
            runtime.raw(b'ng","version":1,"id":2}\n');assert runtime.read()['type']=='pong';runtime.close()
        elif mode in ['eof','partial-eof']:
            if mode=='partial-eof':runtime.raw(frame(dict(type='ping',version=1,id=2)).rstrip(b'\n'))
            runtime.p.stdin.close()
            if mode=='partial-eof':assert runtime.read()['type']=='pong'
            runtime.wait()
        elif mode=='empty-line':
            runtime.raw(b'\n');assert runtime.read()['error']=='malformed request';runtime.close()
        else:
            ping=frame(dict(type='ping',version=1,id=2))
            if mode=='exact-line-bound':
                runtime.raw(b' '*(65536-len(ping))+ping);assert runtime.read()['type']=='pong';runtime.close()
            else:
                runtime.raw(b' ' * 65537);runtime.wait(1)
        results.append(dict(case=mode,passed=True));persist()
    finally:runtime.kill()

for mode in ['live','profile']:
    trace=OUT/(mode+'.jsonl'); env=dict(ENV,WSH_TRACE_FILE=str(trace))
    if mode=='profile':env['WSH_PROFILE_STARTED_UNIX_US']=str(time.time_ns()//1000)
    runtime=Runtime(env)
    try:
        for generation in [1,2]:
            runtime.send(dict(refresh,generation=generation,id=generation));assert runtime.read()['type']=='snapshot'
        runtime.close(); events=[json.loads(line) for line in trace.read_text().splitlines()]
        assert trace.stat().st_mode&0o777==0o600
        names=[e['event'] for e in events]
        assert names.count('refresh-received')==2 and names.count('worker-completed')==2 and names[-1]=='runtime-stopping',names
        snapshots=[e for e in events if e['event']=='snapshot-published'];assert [s['prompt_changed'] for s in snapshots]==[True,False]
        for generation in [1,2]:
            specific=[e['event'] for e in events if e.get('generation')==generation]
            assert specific==['refresh-received','snapshot-published','worker-completed'],specific
        assert str(repo) not in trace.read_text() and os.fsencode(repo).hex() not in trace.read_text()
        results.append(dict(case='trace-'+mode,passed=True,events=events));persist()
    finally:runtime.kill()

for mode in ['symlink','fifo','directory','oversized']:
    trace=OUT/('trace-'+mode)
    if mode=='symlink':trace.symlink_to(OUT/'live.jsonl')
    elif mode=='fifo':os.mkfifo(trace)
    elif mode=='directory':trace.mkdir()
    else:
        with trace.open('wb') as f:f.truncate(8*1024*1024)
    p=subprocess.run(args,env=dict(ENV,WSH_TRACE_FILE=str(trace)),input=b'',capture_output=True,timeout=3)
    assert p.returncode==1 and b'Sanitizer' not in p.stderr and b'runtime error:' not in p.stderr
    results.append(dict(case='reject-trace-'+mode,passed=True,stderr=p.stderr.decode()));persist()

# A real Git command followed by a surviving descendant makes cancellation observable.
bin=OUT/'bin';bin.mkdir();(bin/'git').write_text('#!/bin/sh\n/usr/bin/git "$@" || exit\nsleep 30 &\nprintf "%s %s\\n" "$$" "$!" > "$WSH_PIDS"\nwait\n');(bin/'git').chmod(0o755)
for mode in ['signal','active-eof','parent-death']:
    pids=OUT/(mode+'.pids');env=dict(ENV,PATH=str(bin)+':/usr/bin:/bin',WSH_PIDS=str(pids))
    parent=None;runtime=None
    try:
        if mode=='parent-death':
            script=OUT/'parent.py';script.write_text('import subprocess,sys,time,json\np=subprocess.Popen(json.loads(sys.argv[1]),stdin=subprocess.PIPE,stdout=subprocess.PIPE)\nassert b"ready" in p.stdout.readline()\np.stdin.write(bytes.fromhex(sys.argv[2]));p.stdin.flush()\nopen(sys.argv[3],"w").write(str(p.pid))\ntime.sleep(30)\n')
            marker=OUT/'runtime.pid';parent=subprocess.Popen([sys.executable,script,json.dumps(args),frame(refresh).hex(),marker],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        else:
            runtime=Runtime(env);runtime.send(refresh)
        until=time.monotonic()+3
        while not pids.exists():assert time.monotonic()<until;time.sleep(.005)
        group,descendant=map(int,pids.read_text().split());started=time.monotonic()
        if mode=='parent-death':parent.kill();parent.wait();helper=int(marker.read_text())
        elif mode=='signal':runtime.p.send_signal(signal.SIGTERM);runtime.wait()
        else:runtime.p.stdin.close();runtime.wait()
        until=time.monotonic()+3
        watched=[group,descendant]+([helper] if mode=='parent-death' else [])
        while any(Path(f'/proc/{pid}').exists() for pid in watched) and time.monotonic()<until:time.sleep(.005)
        assert not any(Path(f'/proc/{pid}').exists() for pid in watched),watched
        elapsed=time.monotonic()-started;assert elapsed<3
        if parent:assert not parent.stderr.read()
        results.append(dict(case=mode,passed=True,cleanup_seconds=elapsed));persist()
    finally:
        if runtime:runtime.kill()
        if parent and parent.poll() is None:parent.kill();parent.wait()
        if pids.exists():
            try:os.killpg(int(pids.read_text().split()[0]),signal.SIGKILL)
            except ProcessLookupError:pass
(OUT/'metadata.json').write_text(json.dumps(dict(runtime_sha256=hashlib.sha256(BINARY.read_bytes()).hexdigest(),command=sys.argv),indent=2)+'\n')
print(f'PASS: {len(results)} lifecycle, trace, bounds and process-cleanup cases')
