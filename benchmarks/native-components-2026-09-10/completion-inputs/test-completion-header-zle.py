#!/usr/bin/env python3
"""Real compinit security-preserving header experiment through first and second Tab."""
import importlib.util
import json
import math
import os
from pathlib import Path
import pty
import shlex
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
BUNDLE,PROTO,OUT=[Path(p).resolve() for p in sys.argv[1:4]]
MODE=sys.argv[4]
spec=importlib.util.spec_from_file_location('pty_fixture',ROOT/'benchmarks/deferred-completion-2026-09-06/run.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base);base.OUT=OUT
VARIANTS=['baseline']+[f'{owner}-{state}' for owner in ('control','candidate') for state in ('cold','warm','stale','unusable')]
ALL=VARIANTS+['candidate-vi','candidate-z-first','custom-tab','existing']
CONFIG=base.CONFIG
block='''if [[ $COMP_CASE == deferred-* || $COMP_CASE == existing || $COMP_CASE == custom-tab || $COMP_CASE == vi || $COMP_CASE == z-first ]]; then
  source "$HOME/deferred.zsh"
fi
'''
assert block in CONFIG
CONFIG=CONFIG.replace(block,'').replace('[[ $COMP_CASE == vi ]]','[[ $COMP_CASE == candidate-vi ]]')
CONFIG+='''
if [[ $COMP_CASE == control-* ]]; then
 autoload -Uz compinit
 compinit -i -d "$HOME/dump"
elif [[ $COMP_CASE == candidate-* ]]; then
 functions[compinit]="$(< $WSH_COMPINIT_PROTOTYPE)"
 compinit -i -d "$HOME/dump"
fi
'''
class Shell(base.Shell):
    def __init__(self,variant,label):
        self.label=label;self.output=bytearray();self.home=OUT/'work'/variant
        env=dict(PATH='/usr/bin:/bin',HOME=str(self.home),ZDOTDIR=str(self.home),FPATH=str(next((BUNDLE/'share/zsh').glob('*/functions'))),TERM='xterm-256color',LC_ALL='C.UTF-8',WSH_THEME='',COMP_CASE=variant,WSH_COMPINIT_PROTOTYPE=str(PROTO/'compinit'))
        env.update({k:v for k,v in os.environ.items() if k.endswith('SAN_OPTIONS')})
        self.started=time.monotonic_ns();self.pid,self.fd=pty.fork()
        if self.pid==0:
            os.chdir(OUT/'work/fixture');os.sched_setaffinity(0,{0});os.execve(BUNDLE/'bin/wsh',[str(BUNDLE/'bin/wsh'),'-di'],env)
        self.wait(base.READY);self.startup_ms=(time.monotonic_ns()-self.started)/1e6

def reset(variant):
    dump=OUT/'work'/variant/'dump'
    if variant.endswith('-cold'):dump.unlink(missing_ok=True)
    elif variant.endswith('-stale'):dump.write_bytes((PROTO/'seed').read_bytes().replace(b'#files: ',b'#files: 9',1))

def prepare():
    OUT.mkdir(parents=True);(OUT/'work').mkdir();(OUT/'transcripts').mkdir()
    fixture=OUT/'work/fixture';fixture.mkdir();(fixture/'path with spaces').mkdir();(fixture/'project alpha').mkdir()
    for args in [('init','-qb','main'),('-c','user.name=Completion','-c','user.email=completion@wsh.invalid','commit','--allow-empty','-qm','seed'),('branch','wsh-native-completion-unique')]:subprocess.run(['git','-C',fixture,*args],check=True)
    for variant in ALL:
        home=OUT/'work'/variant;home.mkdir();(home/'.zshrc').write_text(CONFIG)
        (home/'jump-data').write_text(str(fixture/'project alpha')+'|10|'+str(int(time.time()))+'\n')
        if variant.endswith('-unusable'):(home/'dump').mkdir()
        else:(home/'dump').write_bytes((PROTO/'seed').read_bytes())
        reset(variant)

def correctness():
    rows=[]
    for variant in ALL:
        shell=Shell(variant,'correctness-'+variant)
        try:
            before=shell.state()
            if variant=='custom-tab':
                value,_=shell.complete('x');assert value=='xCUSTOMTAB' and before[2]=='0';rows.append(dict(variant=variant,passed=True));continue
            if variant=='baseline':
                assert before[2]=='0';rows.append(dict(variant=variant,passed=True));continue
            if variant=='candidate-z-first':
                value,_=shell.complete('z alpha');assert shlex.split(value)==['z',str(OUT/'work/fixture/project alpha')],value
            for command,expected in [('git switch wsh-native-','git switch wsh-native-completion-unique '),('print path','print path\\ with\\ spaces/')]:
                value,_=shell.complete(command);assert value==expected,(variant,value,expected)
            value,_=shell.complete('z alpha');assert shlex.split(value)==['z',str(OUT/'work/fixture/project alpha')],(variant,value)
            value,_=shell.capture(b'echo \x18');assert value=='echo CUSTOM'
            value,_=shell.capture(b'print -r -- DEFER_AUTOSUGGEST\x1bOA');assert 'DEFER_AUTOSUGGEST_COMPLETE' in value,(variant,value)
            rows.append(dict(variant=variant,passed=True,state=before))
        finally:shell.close();(OUT/'correctness.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(f'PASS: {len(rows)} real ZLE completion/cache and widget composition cases')

def measure():
    assert len(json.loads((OUT/'correctness.json').read_text()))==len(ALL)
    rows=[]
    for pair in range(50):
        for variant in (VARIANTS if pair%2==0 else list(reversed(VARIANTS))):
            reset(variant);shell=Shell(variant,f'measure-{pair}-{variant}')
            try:
                row=dict(pair=pair,variant=variant,startup_ms=shell.startup_ms)
                if variant!='baseline':
                    first,ms=shell.complete('git switch wsh-native-');second,ms2=shell.complete('git switch wsh-native-')
                    assert first==second=='git switch wsh-native-completion-unique '
                    row.update(first_tab_ms=ms,second_tab_ms=ms2)
                rows.append(row)
            finally:shell.close()
    def q(values):return sorted(values)[math.ceil(len(values)*.95)-1]
    summary={v:{k:q([r[k] for r in rows if r['variant']==v]) for k in (['startup_ms'] if v=='baseline' else ['startup_ms','first_tab_ms','second_tab_ms'])} for v in VARIANTS}
    for v in VARIANTS[1:]:
        s=summary[v];s['startup_overhead_ms']=s['startup_ms']-summary['baseline']['startup_ms'];s['startup_limit_ms']=20 if v.endswith('-warm') else 100
        s['passed']=s['startup_overhead_ms']<=s['startup_limit_ms'] and s['first_tab_ms']<=100 and s['second_tab_ms']<=100
    (OUT/'samples.json').write_text(json.dumps(rows,indent=2)+'\n');(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if MODE=='correctness':prepare();correctness()
elif MODE=='measure':measure()
else:raise SystemExit('correctness or measure')
