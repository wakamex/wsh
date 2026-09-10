#!/usr/bin/env python3
"""Measure shared recognition with all five recognized upstream plugins loaded."""
import hashlib
import json
import sys
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
CONTROL=Path(sys.argv[1]).resolve()
BUNDLE=Path(sys.argv[2]).resolve()
OUT=Path(sys.argv[3]).resolve();OUT.mkdir(parents=True,exist_ok=True)
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


with tempfile.TemporaryDirectory(prefix='wsh-native-startup-measure-') as directory:
    home=Path(directory)
    env={'PATH':'/usr/bin:/bin','HOME':directory,'ZDOTDIR':directory,'TERM':'xterm-256color','LC_ALL':'C.UTF-8','TZ':'UTC','WSH_STATE_ROOT':str(home/'no-state')}
    import shlex
    sources = [
        ROOT/'third_party/zsh-z/z.plugin.zsh',
        ROOT/'third_party/zsh-history-substring-search/zsh-history-substring-search.zsh',
        ROOT/'third_party/zsh-autosuggestions/known-0.7.0.zsh',
        ROOT/'third_party/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh',
        ROOT/'third_party/oh-my-zsh-git-prompt/git-prompt.plugin.zsh',
    ]
    config='PROMPT="NATIVE> "\nZSHZ_DATA=$HOME/jump-data\n' + ''.join('source '+shlex.quote(str(p))+'\n' for p in sources)
    (home/'.zshenv').write_text('unsetopt globalrcs\n')
    (home/'.zshrc').write_text(config)
    samples=[]
    for theme in ('','minimal'):
        for pair in range(50):
            for variant in (('control','native') if pair%2==0 else ('native','control')):
                environment=dict(env,WSH_THEME=theme)
                NATIVE=(CONTROL if variant=='control' else BUNDLE)/'bin/wsh'
                arguments=['-d','-i']
                before,pid,fd=start(arguments,environment,home)
                try:
                    output=wait(fd);elapsed=(time.monotonic_ns()-before)/1e6
                    assert os.readlink('/proc/'+str(pid)+'/exe')==str(NATIVE)
                    samples.append({'theme':theme or 'existing','pair':pair,'variant':variant,'readiness_ms':elapsed})
                finally:stop(pid,fd)
    summary={}
    for theme in ('existing','minimal'):
        rows=[row for row in samples if row['theme']==theme]
        data={v:[row['readiness_ms'] for row in rows if row['variant']==v] for v in ('control','native')}
        differences=sorted(data['native'][i]-data['control'][i] for i in range(50))
        summary[theme]={'pairs':50,'paired_p95_ms':differences[47],'gate_ms':3,'passed':differences[47]<=3,
                        'control_median_ms':sorted(data['control'])[24],'native_median_ms':sorted(data['native'])[24]}
    metadata={'command':'python3 native/measure-plugin-catalog.py '+str(CONTROL)+' '+str(BUNDLE)+' '+str(OUT),'cpu':0,'trace_mode':'off','zshrc':config,
              'zshenv':'unsetopt globalrcs\n','source_revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'native_sha256':hashlib.sha256((BUNDLE/'bin/wsh').read_bytes()).hexdigest(),
              'control_sha256':hashlib.sha256((CONTROL/'bin/wsh').read_bytes()).hexdigest(),
              'runtime_sha256':hashlib.sha256((BUNDLE/'bin/wsh-runtime').read_bytes()).hexdigest(),
              'manifest_sha256':hashlib.sha256((BUNDLE/'manifest.json').read_bytes()).hexdigest(),
              'correctness':'primary editable marker and direct native PID; separate startup and contract suites'}
    (OUT/'samples.json').write_text(json.dumps(samples,indent=2)+'\n')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (OUT/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    assert all(result['passed'] for result in summary.values()),summary
