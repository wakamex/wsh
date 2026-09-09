#!/usr/bin/env python3
"""Show why suppressing Zsh's child handler is only a causal diagnostic."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

binary,module,out=[Path(value).resolve() for value in sys.argv[1:]]
script='module_path=($1 $module_path); zmodload wshcollector || exit 2; sleep .03 & pid=$!; wait $pid; print WSH_JOB:$?; zmodload -u wshcollector'
results=[]
for suppress in [False,True]:
    env=dict(PATH='/usr/bin:/bin',HOME=str(out.parent),LC_ALL='C.UTF-8')
    if suppress:env['WSH_PROBE_NO_SIGCHLD']='1'
    started=time.monotonic()
    try:
        result=subprocess.run([binary,'-dfc',script,'probe',str(module.parent)],env=env,capture_output=True,timeout=3)
        row=dict(suppressed=suppress,status=result.returncode,stdout=result.stdout.decode(),stderr=result.stderr.decode(),timed_out=False)
    except subprocess.TimeoutExpired as e:
        row=dict(suppressed=suppress,timed_out=True,stdout=(e.stdout or b'').decode(),stderr=(e.stderr or b'').decode())
    row['seconds']=time.monotonic()-started;results.append(row)
assert results[0]['status']==0 and results[0]['stdout']=='WSH_JOB:0\n'
assert results[1]['timed_out']
out.write_text(json.dumps(results,indent=2)+'\n');print('PASS: ordinary wait works; suppressed SIGCHLD hangs and is rejected')
