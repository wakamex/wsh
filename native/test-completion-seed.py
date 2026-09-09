#!/usr/bin/env python3
"""Actual ZLE comparison of native initialization with an installation dump."""
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import pty
import select
import shlex
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
BUNDLE,PROTO,OUT=[Path(x).resolve() for x in sys.argv[1:4]]
mode=sys.argv[4]
spec=importlib.util.spec_from_file_location('deferred_fixture',ROOT/'benchmarks/deferred-completion-2026-09-06/run.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base);base.OUT=OUT
VARIANTS=['baseline','eager-cold','eager-warm','seed','seed-stale','seed-unusable']
ALL=[*VARIANTS,'seed-vi','seed-z-first','custom-tab','existing']
config=base.CONFIG
block='''if [[ $COMP_CASE == deferred-* || $COMP_CASE == existing || $COMP_CASE == custom-tab || $COMP_CASE == vi || $COMP_CASE == z-first ]]; then
  source "$HOME/deferred.zsh"
fi
'''
assert block in config;config=config.replace(block,'').replace('[[ $COMP_CASE == vi ]]','[[ $COMP_CASE == seed-vi ]]')
config+='''
if [[ $COMP_CASE != baseline && $COMP_CASE != eager-* && ! -v 'functions[compdef]' && $(bindkey '^I') == *expand-or-complete* ]]; then
  functions[compinit]="$(< $WSH_COMPINIT_PROTOTYPE)"
  compinit -i -R -d "$HOME/seed"
  typeset -g _comp_dumpfile="${ZDOTDIR:-$HOME}/.zcompdump"
fi
'''
class Shell(base.Shell):
    def __init__(self,variant,label):
        self.label=label;self.output=bytearray();self.home=OUT/'work'/variant
        env=dict(PATH='/usr/bin:/bin',HOME=str(self.home),ZDOTDIR=str(self.home),FPATH=str(next((BUNDLE/'share/zsh').glob('*/functions'))),TERM='xterm-256color',LC_ALL='C.UTF-8',WSH_THEME='',COMP_CASE=variant,WSH_COMPINIT_PROTOTYPE=str(PROTO/'compinit'))
        self.started=time.monotonic_ns();self.pid,self.fd=pty.fork()
        if self.pid==0:
            os.chdir(OUT/'work/fixture');os.sched_setaffinity(0,{0});os.execve(BUNDLE/'bin/wsh',[str(BUNDLE/'bin/wsh'),'-di'],env)
        self.wait(base.READY);self.startup_ms=(time.monotonic_ns()-self.started)/1e6

def prepare():
    OUT.mkdir(parents=True);(OUT/'work').mkdir();(OUT/'transcripts').mkdir()
    fixture=OUT/'work/fixture';fixture.mkdir();(fixture/'path with spaces').mkdir();(fixture/'project alpha').mkdir()
    for args in [('init','-qb','main'),('-c','user.name=Completion','-c','user.email=completion@wsh.invalid','commit','--allow-empty','-qm','seed'),('branch','wsh-native-completion-unique')]:subprocess.run(['git','-C',fixture,*args],check=True)
    for variant in ALL:
        home=OUT/'work'/variant;home.mkdir();(home/'.zshrc').write_text(config)
        (home/'jump-data').write_text(str(fixture/'project alpha')+'|10|'+str(int(time.time()))+'\n')
        if variant!='seed-unusable':
            seed=(PROTO/'seed').read_bytes()
            if variant=='seed-stale':seed=seed.replace(b'#files: ',b'#files: 9',1)
            (home/'seed').write_bytes(seed)
        else:(home/'seed').mkdir()
    (OUT/'metadata.json').write_text(json.dumps(dict(bundle_sha256=hashlib.sha256((BUNDLE/'manifest.json').read_bytes()).hexdigest(),binary_sha256=hashlib.sha256((BUNDLE/'bin/wsh').read_bytes()).hexdigest(),prototype_sha256=hashlib.sha256((PROTO/'compinit').read_bytes()).hexdigest(),seed_sha256=hashlib.sha256((PROTO/'seed').read_bytes()).hexdigest(),config=config,command=sys.argv,cpu=0,trace_mode='off'),indent=2)+'\n')

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
            if variant=='seed-z-first':
                value,_=shell.complete('z alpha');assert shlex.split(value)==['z',str(OUT/'work/fixture/project alpha')],value
            for command,expected in [('git switch wsh-native-','git switch wsh-native-completion-unique '),('print path','print path\\ with\\ spaces/')]:
                value,_=shell.complete(command);assert value==expected,(variant,value,expected)
            value,_=shell.complete('z alpha');assert shlex.split(value)==['z',str(OUT/'work/fixture/project alpha')],(variant,value)
            value,_=shell.capture(b'echo \x18');assert value=='echo CUSTOM'
            value,_=shell.capture(b'print -r -- DEFER_AUTOSUGGEST\x1bOA');assert 'DEFER_AUTOSUGGEST_COMPLETE' in value,(variant,value)
            details={}
            if variant!='seed-vi':
                offset=len(shell.output);os.write(shell.fd,b'print -r -- DEFER_AUTO');shell.wait(b'SUGGEST_COMPLETE',offset)
                suggestion=shell.state();assert suggestion[0]=='SUGGEST_COMPLETE',suggestion
                value,_=shell.capture(b'\x05');assert value=='print -r -- DEFER_AUTOSUGGEST_COMPLETE',value
                os.write(shell.fd,b'nonexistent_seed_command');time.sleep(.03);highlighted=shell.state();assert int(highlighted[1])>0,highlighted;shell.capture(b'')
                details=dict(suggestion=suggestion,highlighted=highlighted)
            rows.append(dict(variant=variant,passed=True,state=before,**details))
        finally:shell.close();(OUT/'correctness.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(f'PASS: {len(rows)} native ZLE completion and composition cases')

def measure():
    assert len(json.loads((OUT/'correctness.json').read_text()))==len(ALL)
    rows=[]
    for pair in range(50):
        for variant in (VARIANTS if pair%2==0 else list(reversed(VARIANTS))):
            if variant=='eager-cold':(OUT/'work'/variant/'.zcompdump').unlink(missing_ok=True)
            shell=Shell(variant,f'measure-{pair}-{variant}')
            try:
                row=dict(pair=pair,variant=variant,startup_ms=shell.startup_ms)
                if variant!='baseline':
                    first,first_ms=shell.complete('git switch wsh-native-');second,second_ms=shell.complete('git switch wsh-native-')
                    assert first==second=='git switch wsh-native-completion-unique '
                    row.update(first_tab_ms=first_ms,second_tab_ms=second_ms)
                rows.append(row)
            finally:shell.close()
    def q(values):return sorted(values)[math.ceil(len(values)*.95)-1]
    summary={variant:{key:q([r[key] for r in rows if r['variant']==variant]) for key in (['startup_ms'] if variant=='baseline' else ['startup_ms','first_tab_ms','second_tab_ms'])} for variant in VARIANTS}
    baseline=summary['baseline']['startup_ms']
    for variant in VARIANTS[1:]:
        s=summary[variant];s['startup_overhead_ms']=s['startup_ms']-baseline;s['startup_limit_ms']=20 if variant in ['eager-warm','seed'] else 100
        s['passed']=s['startup_overhead_ms']<=s['startup_limit_ms'] and s['first_tab_ms']<=100 and s['second_tab_ms']<=100
    (OUT/'samples.json').write_text(json.dumps(rows,indent=2)+'\n');(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if mode=='correctness':prepare();correctness()
elif mode=='measure':measure()
else:raise SystemExit('expected correctness or measure')
