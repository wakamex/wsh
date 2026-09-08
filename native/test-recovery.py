#!/usr/bin/env python3
"""Empty-home and unavailable-optional-component interactive recovery checks."""
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import sys
import tempfile
import time

BUNDLE=Path(sys.argv[1]).resolve()
OUT=Path(sys.argv[2]).resolve();OUT.mkdir(parents=True,exist_ok=True)
results=[]
with tempfile.TemporaryDirectory(prefix='wsh-native-recovery-') as directory:
    root=Path(directory)
    for mode in ('empty-home','missing-runtime','unreadable-runtime','incompatible-runtime','missing-integration'):
        home=root/(mode+'-home');home.mkdir()
        installation=root/mode;shutil.copytree(BUNDLE,installation)
        if mode!='empty-home':
            (home/'.zshenv').write_text('unsetopt globalrcs\n')
            (home/'.zshrc').write_text('PROMPT="SAFE> "\nWSH_THEME=minimal\n')
        if mode=='missing-runtime':(installation/'bin/wsh-runtime').unlink()
        if mode=='unreadable-runtime':(installation/'bin/wsh-runtime').chmod(0)
        if mode=='incompatible-runtime':(installation/'bin/wsh-runtime').write_text('#!/bin/sh\nexit 64\n')
        if mode=='missing-integration':shutil.rmtree(installation/'share/wsh')
        env={'PATH':'/usr/bin:/bin','HOME':str(home),'ZDOTDIR':str(home),'TERM':'xterm-256color','LC_ALL':'C.UTF-8','WSH_STATE_ROOT':str(root/'no-state')}
        env.update({key:os.environ[key] for key in ('ASAN_OPTIONS','UBSAN_OPTIONS') if key in os.environ})
        pid,fd=pty.fork()
        if not pid:
            os.chdir(home)
            os.execve(installation/'bin/wsh',['-wsh'],env)
        output=bytearray();started=time.monotonic();deadline=started+8
        try:
            while b'\x1b]133;B' not in output or b'\x1b]133;P;k=i' not in output:
                assert time.monotonic()<deadline,(mode,bytes(output))
                if select.select([fd],[],[],.05)[0]:output.extend(os.read(fd,65536))
            readiness=time.monotonic()-started
            assert b'zsh-newuser-install' not in output,(mode,bytes(output))
            os.write(fd,b'print -r -- RECOVERY:$ZSH_VERSION; exit 23\n')
            while b'RECOVERY:5.9.999.3-test' not in output:
                assert time.monotonic()<deadline,(mode,bytes(output))
                if select.select([fd],[],[],.05)[0]:output.extend(os.read(fd,65536))
            _,status=os.waitpid(pid,0);assert os.waitstatus_to_exitcode(status)==23,(mode,status)
            pid=None
            if mode=='empty-home':
                assert not any((home/name).exists() for name in ('.zshenv','.zprofile','.zshrc','.zlogin'))
            results.append({'case':mode,'status':23,'readiness_seconds':readiness,'configuration_created':False})
        finally:
            if pid is not None:
                try:os.killpg(pid,signal.SIGHUP)
                except ProcessLookupError:pass
                os.waitpid(pid,0)
            os.close(fd)
            (OUT/(mode+'.bin')).write_bytes(output)
        (OUT/'recovery-results.json').write_text(json.dumps(results,indent=2)+'\n')
print('PASS: empty-home login and four unavailable optional-component paths reach a usable native prompt')
