#!/usr/bin/env python3
"""Failure, resource, cleanup and real native global-startup boundaries."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
BINARY=Path(sys.argv[1] if len(sys.argv)>1 else '/var/tmp/wsh-native-tools/installation/bin/wsh')
OUT=Path('/var/tmp/wsh-native-tools/doctor-evidence')
results=[]
with tempfile.TemporaryDirectory(prefix='wsh-doctor-boundaries-') as directory:
    home=Path(directory)
    env={'PATH':'/usr/bin:/bin','HOME':directory,'ZDOTDIR':directory,'TERM':'xterm-256color','LC_ALL':'C.UTF-8',
         'WSH_STATE_ROOT':str(home/'absent-state'),'ASAN_OPTIONS':'detect_leaks=0:abort_on_error=1',
         'UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
    (home/'.zshenv').write_text('unsetopt globalrcs\n')
    def run(config='',arguments=('--wsh-doctor',), binary=BINARY,environment=env):
        (home/'.zshrc').write_text(config)
        return subprocess.run([binary,*arguments],env=environment,input=b'',capture_output=True,timeout=13)
    for state in ('absent','corrupt','unreadable'):
        state_dir=home/'absent-state'
        if state!='absent':
            state_dir.mkdir(exist_ok=True);(state_dir/'active.json').write_text('{broken')
        if state=='unreadable':state_dir.chmod(0)
        result=run()
        assert result.returncode==0 and not result.stderr,(state,result)
        state_dir.chmod(0o700) if state_dir.exists() else None
        results.append(state+' activation state ignored')
    for argument in (b'extra',b'\xff',b'--'):
        result=run(arguments=('--wsh-doctor',argument))
        assert result.returncode==2 and not result.stdout
    results.append('doctor extra and non-UTF-8 arguments rejected')
    for value in ('invalid', 'x'*100000, '\\e]52;c;secret\\a'):
        config="typeset -gr WSH_HISTORY_SUBSTRING_SEARCH_OWNER=$'"+value+"'\n"
        result=run(config)
        assert result.returncode==1 and not result.stdout and b'secret' not in result.stderr,result
    results.append('inconsistent, huge and control-containing ownership fails without reflecting input')
    result=run('sleep 30 &\nprint -r -- $! > $HOME/background.pid\n')
    assert result.returncode==0,result
    pid=int((home/'background.pid').read_text())
    def alive(pid):
        try:return Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()[0]!='Z'
        except FileNotFoundError:return False
    deadline=time.monotonic()+2
    while alive(pid) and time.monotonic()<deadline:time.sleep(.01)
    assert not alive(pid),pid
    results.append('background child is no longer running after successful doctor')
    # Bind a real global startup file in a private mount namespace. No host file changes.
    global_file=home/'global.zshrc';global_file.write_text('typeset -g WSH_GLOBAL_DOCTOR_FIXTURE=seen\n')
    empty=home/'empty';empty.write_text('')
    (home/'.zshenv').write_text('')
    (home/'.zshrc').write_text('[[ ${WSH_GLOBAL_DOCTOR_FIXTURE-} == seen ]] || exit 42\n')
    for present in (True,False):
        command=['bwrap','--unshare-user','--unshare-pid','--die-with-parent','--ro-bind','/','/',
                 '--dev-bind','/dev','/dev','--proc','/proc','--ro-bind',str(global_file if present else empty),'/etc/zshrc','--',str(BINARY),'--wsh-doctor']
        result=subprocess.run(command,env=env,input=b'',capture_output=True,timeout=13)
        assert result.returncode==(0 if present else 1),(present,result)
    results.append('real global startup is read; empty-file counterfactual fails the startup assertion')
    (home/'.zshrc').write_text('');(home/'.zshenv').write_text('unsetopt globalrcs\n')
    relocated=home/'wsh';shutil.copy2(BINARY,relocated)
    result=run(binary=relocated)
    assert result.returncode==0 and b'does not expose plugin ownership diagnostics' in result.stdout,result
    results.append('missing installed integration returns an explicit unavailable diagnostic')
(OUT/('doctor-boundaries-sanitized.json' if 'sanitized' in BINARY.name else 'doctor-boundaries.json')).write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
