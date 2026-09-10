#!/usr/bin/env python3
"""Run existing component contracts through native invocation, not a manager shim."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=Path(sys.argv[1]).resolve()
OUT=Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True,exist_ok=True)
ZSH=Path(os.environ.get('WSH_TEST_ZSH', '/usr/bin/zsh'))
RAW=Path(os.environ.get('WSH_REFERENCE_ZSH', '/usr/bin/zsh'))
OMZ=os.environ.get('WSH_TEST_OMZ')
results=[]
for name in ('history-substring-search','autosuggestions','syntax-highlighting','plugin-doctor','directory-jump','named-themes','zsh-config-coexistence','prompt-ownership','foreground-startup'):
    test=ROOT/'tests'/(name+'.zsh')
    command=[ZSH,'-df',test,BUNDLE]
    if name=='zsh-config-coexistence':command.append('present')
    if name=='foreground-startup':command.append('candidate')
    if OMZ and name in ('directory-jump','prompt-ownership'):command.append(OMZ)
    with (OUT/(name+'.log')).open('wb') as log:
        result=subprocess.run([str(value) for value in command],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180,
                              env=dict(os.environ,WSH_EXPECT_NATIVE_TERMINAL_PASS='1',WSH_REFERENCE_ZSH=str(RAW)))
    results.append({'test':name,'command':[str(value) for value in command],'status':result.returncode})
    (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(name,result.returncode,flush=True)
if any(row['status'] for row in results):raise SystemExit(1)
