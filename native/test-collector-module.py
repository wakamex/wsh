#!/usr/bin/env python3
"""Probe actual Zsh child ownership against the unchanged C helper control."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
ZSH,MODULE,RUNTIME,OUT=[Path(value).resolve() for value in sys.argv[1:]]
OUT.mkdir(parents=True);repo=OUT/'repo';repo.mkdir()
env=dict(PATH='/usr/bin:/bin',HOME=str(OUT),LC_ALL='C.UTF-8',ZDOTDIR=str(OUT))
if 'WSH_PROBE_NO_SIGCHLD' in os.environ:env['WSH_PROBE_NO_SIGCHLD']='1'
env.update({key:os.environ[key] for key in ['ASAN_OPTIONS','UBSAN_OPTIONS'] if key in os.environ})
for args in [('init','-qb','main'),('config','user.name','probe'),('config','user.email','probe@wsh.invalid')]:subprocess.run(['git','-C',repo,*args],env=env,check=True)
(repo/'file').write_text('seed\n');subprocess.run(['git','-C',repo,'add','file'],env=env,check=True);subprocess.run(['git','-C',repo,'commit','-qm','seed'],env=env,check=True)
script=OUT/'probe.zsh';script.write_text('''module_path=($1 $module_path)
zmodload wshcollector || exit 2
repeat 100; do
  wsh-collector-probe start "$2" || exit 3
  while ! wsh-collector-probe poll; do :; done
done
zmodload -u wshcollector || exit 4
''')
result=subprocess.run([ZSH,'-df',script,MODULE.parent,repo],env=env,capture_output=True,timeout=30)
(OUT/'stdout').write_bytes(result.stdout);(OUT/'stderr').write_bytes(result.stderr)
lines=result.stdout.decode().splitlines();assert result.returncode==0 and len(lines)==100,(result.returncode,result.stdout,result.stderr)
control=[]
p=subprocess.Popen([RUNTIME,'serve','--theme',ROOT/'themes/minimal.toml'],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try:
 assert json.loads(p.stdout.readline())['type']=='ready'
 for generation in range(1,101):
  request=dict(type='refresh',version=1,id=generation,generation=generation,cwd_hex=os.fsencode(repo).hex(),exit_status=0,duration_ms=None,privileged=False,reset_transient=False)
  p.stdin.write(json.dumps(request).encode()+b'\n');p.stdin.flush();response=json.loads(p.stdout.readline());assert response['type']=='snapshot' and response['snapshot']['found'];control.append(response)
 p.stdin.write(b'{"type":"shutdown","version":1,"id":0}\n');p.stdin.flush();assert json.loads(p.stdout.readline())['type']=='stopping';assert p.wait(timeout=3)==0 and not p.stderr.read()
finally:
 if p.poll() is None:p.kill();p.wait()
summary=dict(module_cases=len(lines),module_successes=sum(line=='WSH_PROBE:1:1:ok' for line in lines),module_errors=[line for line in lines if line!='WSH_PROBE:1:1:ok'],helper_successes=len(control),binaries={name:dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for name,path in [('zsh',ZSH),('module',MODULE),('helper',RUNTIME)]},command=sys.argv)
(OUT/'results.json').write_text(json.dumps(summary,indent=2)+'\n');(OUT/'control.json').write_text(json.dumps(control,indent=2)+'\n');print(json.dumps(summary,indent=2))
