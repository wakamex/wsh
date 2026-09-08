#!/usr/bin/env python3
"""Real Git output faults preserve runtime liveness, locks and bounded collection."""
import json,os,select,signal,subprocess,time,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];runtime=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir(parents=True);results=[]
repo=out/'repo';repo.mkdir()
for args in [['init','-q','-b','main'],['config','user.name','output-test'],['config','user.email','output@wsh.invalid']]:subprocess.run(['git','-C',repo,*args],check=True)
(repo/'file').write_text('seed\n')
subprocess.run(['git','-C',repo,'add','file'],check=True)
subprocess.run(['git','-C',repo,'commit','-qm','seed'],check=True)
for name,script in [('oversized','/usr/bin/git "$@" || exit\n/usr/bin/head -c 4194305 /dev/zero\n'),('invalid-utf8','/usr/bin/git "$@" || exit\nprintf "\\377"\n'),('nonzero','/usr/bin/git "$@" || exit\nexit 42\n'),('closed-output-slow','/usr/bin/git "$@" || exit\nexec 1>&-\nexec /usr/bin/sleep 30\n')]:
    case=out/name;case.mkdir();binary=case/'git';binary.write_text('#!/bin/sh\n[ "$GIT_OPTIONAL_LOCKS" = 0 ] || exit 99\n'+script);binary.chmod(0o755)
    p=subprocess.Popen([runtime,'serve','--theme',root/'themes/minimal.toml'],env=dict(os.environ,PATH=str(case)+':/usr/bin:/bin'),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    buffer=bytearray()
    def read():
        deadline=time.monotonic()+3
        while b'\n' not in buffer:
            assert time.monotonic()<deadline,(name,bytes(buffer))
            if select.select([p.stdout],[],[],.05)[0]:
                b=os.read(p.stdout.fileno(),65536);assert b;b and buffer.extend(b)
        line,_,rest=buffer.partition(b'\n');buffer[:]=rest;return json.loads(line)
    def send(v):p.stdin.write(json.dumps(v).encode()+b'\n');p.stdin.flush()
    try:
        assert read()['type']=='ready'
        t=time.monotonic();send(dict(type='refresh',version=1,id=1,generation=1,cwd_hex=os.fsencode(repo).hex(),exit_status=0,duration_ms=None,privileged=False,reset_transient=False));response=read();elapsed=time.monotonic()-t
        assert response['type']=='error',response
        if name=='oversized':assert '4194304' in response['error'],response
        if name=='invalid-utf8':assert 'UTF-8' in response['error'],response
        if name=='nonzero':assert '42' in response['error'],response
        if name=='closed-output-slow':assert elapsed<3
        send(dict(type='ping',version=1,id=2));assert read()['type']=='pong'
        send(dict(type='shutdown',version=1,id=3));assert read()['type']=='stopping';assert p.wait(timeout=3)==0
        results.append(dict(case=name,response=response,elapsed_seconds=elapsed,status=p.returncode))
    finally:
        if p.poll() is None:p.kill();p.wait()
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');print('PASS: four real-Git output faults, optional locks, runtime liveness and bounded timeout')
