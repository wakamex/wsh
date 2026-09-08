#!/usr/bin/env python3
"""Direct native foreground byte/status checks and paired readiness measurement."""
import hashlib
import json
import math
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
WORK=Path('/var/tmp/wsh-native-tools')
OUT=WORK/'foreground-evidence'
BUNDLE=WORK/'installation'
NATIVE=BUNDLE/'bin/wsh'
READY=b'\x1b]133;B\x1b\\'
PRIMARY=b'\x1b]133;P;k=i'


def wait(fd, marker=READY):
    output=bytearray();deadline=time.monotonic()+8
    while marker not in output or (marker==READY and PRIMARY not in output):
        assert time.monotonic()<deadline,bytes(output)
        if select.select([fd],[],[],.05)[0]:output.extend(os.read(fd,65536))
    return bytes(output)


def start(arguments,environment,home):
    before=time.monotonic_ns();pid,fd=pty.fork()
    if not pid:
        os.chdir(home);os.sched_setaffinity(0,{0})
        os.execve(NATIVE,[os.fsencode(NATIVE),*[os.fsencode(a) for a in arguments]],environment)
    return before,pid,fd


def stop(pid,fd):
    try:os.killpg(pid,signal.SIGHUP)
    except ProcessLookupError:pass
    os.close(fd);os.waitpid(pid,0)


with tempfile.TemporaryDirectory(prefix='wsh-native-foreground-') as directory:
    home=Path(directory)
    env={'PATH':'/usr/bin:/bin','HOME':directory,'ZDOTDIR':directory,'TERM':'xterm-256color','LC_ALL':'C.UTF-8','TZ':'UTC','WSH_STATE_ROOT':str(home/'no-state')}
    config='PROMPT="NATIVE> "\nZSHZ_DATA=$HOME/jump-data\n'
    (home/'.zshenv').write_text('unsetopt globalrcs\n')
    (home/'.zshrc').write_text(config)
    byte_program=home/'program \udcff'
    byte_program.write_text('#!/usr/bin/python3\nimport json,os,sys\nos.write(1,b"ARGV:"+json.dumps([os.fsencode(x).hex() for x in sys.argv]).encode()+b"\\n")\nsys.exit(7)\n')
    byte_program.chmod(0o755)
    values=[b'',b'\xff',b'line\nbreak',b'$(printf INJECTED)',b'%F{red}',b'--wsh-doctor']
    _,pid,fd=start(['--wsh-run','--',byte_program,*values],env,home)
    try:
        output=wait(fd)
        actual=json.loads(output.split(b'ARGV:',1)[1].splitlines()[0])
        assert actual==[os.fsencode(byte_program).hex(),*[value.hex() for value in values]],output
        assert output.count(b'\x1b]133;C')==1 and output.count(b'\x1b]133;D')==1,output
        assert os.readlink('/proc/'+str(pid)+'/exe')==str(NATIVE)
        os.write(fd,b'print -r -- STATUS:$?; exit 23\n')
        output+=wait(fd,b'STATUS:7')
        _,status=os.waitpid(pid,0);assert os.waitstatus_to_exitcode(status)==23
        pid=None
        (OUT/'bytes-and-status.bin').write_bytes(output)
    finally:
        if pid is not None:stop(pid,fd)
        else:os.close(fd)
    for arguments in (['--wsh-run'],['--wsh-run','--'],['--wsh-run','--',''],['--wsh-run','--login','--'],['--wsh-run','--login','--login','--','true'],['--wsh-run',b'\xff']):
        result=subprocess.run([NATIVE,*arguments],env=env,input=b'',capture_output=True,timeout=3)
        assert result.returncode==2 and not result.stdout and b'usage:' in result.stderr,result
    samples=[]
    for theme in ('','minimal'):
        for pair in range(50):
            for variant in (('callback','native') if pair%2==0 else ('native','callback')):
                environment=dict(env,WSH_THEME=theme)
                if variant=='callback':
                    arguments=['-i','-s','--','/usr/bin/true']
                    environment['WSH_RUN_FOREGROUND']='1'
                else:arguments=['--wsh-run','--','/usr/bin/true']
                before,pid,fd=start(arguments,environment,home)
                try:
                    output=wait(fd);elapsed=(time.monotonic_ns()-before)/1e6
                    assert output.count(b'\x1b]133;C')==1 and output.count(b'\x1b]133;D')==1,output
                    assert os.readlink('/proc/'+str(pid)+'/exe')==str(NATIVE)
                    samples.append({'theme':theme or 'existing','pair':pair,'variant':variant,'readiness_ms':elapsed})
                finally:stop(pid,fd)
    summary={}
    for theme in ('existing','minimal'):
        rows=[row for row in samples if row['theme']==theme]
        data={v:[row['readiness_ms'] for row in rows if row['variant']==v] for v in ('callback','native')}
        differences=sorted(data['native'][i]-data['callback'][i] for i in range(50))
        summary[theme]={'pairs':50,'paired_p95_ms':differences[47],'gate_ms':3,'passed':differences[47]<=3,
                        'callback_median_ms':sorted(data['callback'])[24],'native_median_ms':sorted(data['native'])[24]}
    metadata={'command':'python3 native/test-foreground.py','cpu':0,'trace_mode':'off','zshrc':config,
              'zshenv':'unsetopt globalrcs\n','source_revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'native_sha256':hashlib.sha256(NATIVE.read_bytes()).hexdigest(),
              'runtime_sha256':hashlib.sha256((BUNDLE/'bin/wsh-runtime').read_bytes()).hexdigest(),
              'manifest_sha256':hashlib.sha256((BUNDLE/'manifest.json').read_bytes()).hexdigest(),
              'correctness':'exact bytes including non-UTF-8 executable path, status 7, shell exit 23, one C/D marker pair, native PID, six malformed invocations'}
    (OUT/'samples.json').write_text(json.dumps(samples,indent=2)+'\n')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (OUT/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    assert all(result['passed'] for result in summary.values()),summary
