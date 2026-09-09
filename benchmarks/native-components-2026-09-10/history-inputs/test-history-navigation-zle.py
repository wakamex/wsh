#!/usr/bin/env python3
"""Real ZLE navigation parity and paired default/unique editing measurements."""
import importlib.util
import json
import os
from pathlib import Path
import pty
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
BINARY,MODULE,FIXTURE,OUT=[Path(p).resolve() for p in sys.argv[1:5]]
MODE=sys.argv[5]
spec=importlib.util.spec_from_file_location('pty_fixture',ROOT/'benchmarks/deferred-completion-2026-09-06/run.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base);base.OUT=OUT
OUT.mkdir(parents=True,exist_ok=True);(OUT/'transcripts').mkdir(exist_ok=True)
CONFIG=r'''
PROMPT='HISTORY> '
module_path=($WSH_TEST_MODULE $module_path)
zmodload wshhistory
source $WSH_TEST_SOURCE
HISTSIZE=30000
unsetopt hist_ignore_all_dups hist_ignore_dups
HISTORY_SUBSTRING_SEARCH_ENSURE_UNIQUE=$WSH_TEST_UNIQUE
HISTORY_SUBSTRING_SEARCH_FUZZY=$WSH_TEST_FUZZY
HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_TIMEOUT=0
[[ $WSH_TEST_VI == 1 ]] && bindkey -v
bindkey '^P' history-substring-search-up
bindkey '^N' history-substring-search-down
for ((i=0;i<WSH_TEST_COUNT;i++)); do print -s -- "echo duplicate $((i%3))"; done
print -s -- $'echo multiline\nsecond'
print -s -- 'echo é newest'
_custom() { BUFFER+=' CUSTOM'; CURSOR=$#BUFFER; }
zle -N _custom
bindkey '^X' _custom
_capture() {
  print -nr -- $'\x1eBUFFER:'"$BUFFER"$'\x1f'
  BUFFER='' POSTDISPLAY='' CURSOR=0
  _history_substring_search_result=''
  zle redisplay
}
zle -N _capture
bindkey '^G' _capture
'''
class Shell(base.Shell):
    def __init__(self,owner,label,count=100,unique='',fuzzy='',vi=''):
        self.label=label;self.output=bytearray();self.home=OUT/owner
        self.home.mkdir(exist_ok=True);(self.home/'.zshrc').write_text(CONFIG)
        env=dict(PATH='/usr/bin:/bin',HOME=str(self.home),ZDOTDIR=str(self.home),TERM='xterm-256color',LC_ALL='C.UTF-8',WSH_THEME='',WSH_DISABLE_DIRECTORY_JUMP='1',WSH_DISABLE_HISTORY_SUBSTRING_SEARCH='1',WSH_DISABLE_AUTOSUGGESTIONS='1',WSH_TEST_MODULE=str(MODULE),WSH_TEST_SOURCE=str(FIXTURE/f'{owner}.zsh'),WSH_TEST_COUNT=str(count),WSH_TEST_UNIQUE=unique,WSH_TEST_FUZZY=fuzzy,WSH_TEST_VI=vi)
        env.update({k:v for k,v in os.environ.items() if k.endswith('SAN_OPTIONS')})
        self.pid,self.fd=pty.fork()
        if self.pid==0:
            os.chdir(OUT);os.sched_setaffinity(0,{0});os.execve(BINARY,[str(BINARY),'-di'],env)
        self.wait(base.READY)
        assert b'failed' not in self.output and b'ERROR:' not in self.output, self.output
if MODE=='correctness':
    rows=[]
    for unique,fuzzy,vi in [('', '', ''),('1','',''),('','1',''),('','','1')]:
        variants=[]
        for owner in ('control','candidate'):
            shell=Shell(owner,f'{owner}-{len(rows)}',unique=unique,fuzzy=fuzzy,vi=vi)
            try:
                values=[]
                for keys in [b'echo\x10',b'echo\x10\x10',b'echo\x10\x10\x0e',b'absent\x10',b'echo\x18\x10',b'echo multi\x10\x01\x10',b'echo duplicate\x10\x10\x10\x10\x0e',b'\x10\x0e']:
                    value,_=shell.capture(keys);values.append(value)
                variants.append(values)
            finally:shell.close()
        rows.append(dict(config=[unique,fuzzy,vi],variants=variants,equal=variants[0]==variants[1]))
        (OUT/'correctness.json').write_text(json.dumps(rows,indent=2)+'\n')
        assert rows[-1]['equal'],rows[-1]
    print('PASS: 32 paired actual ZLE navigation, custom-widget and multiline cases')
elif MODE=='measure':
    rows=[];summary={}
    for count in (100,10000):
        for unique in ('','1'):
            shells={o:Shell(o,f'measure-{count}-{unique}-{o}',count=count,unique=unique) for o in ('control','candidate')}
            try:
                pairs=[]
                for index in range(50):
                    pair={};values={}
                    for owner in (('control','candidate') if index%2==0 else ('candidate','control')):
                        # Capture clears BUFFER and each edit starts a new search.
                        value,ms=shells[owner].capture(b'echo duplicate\x10\x10\x10\x10')
                        pair[owner]=ms;values[owner]=value
                    assert values['control']==values['candidate'],values
                    pairs.append(pair)
                medians={o:statistics.median(p[o] for p in pairs) for o in shells}
                summary[f'{count}/unique={bool(unique)}']=dict(pairs=pairs,median_ms=medians,paired_p95_delta_ms=sorted(p['candidate']-p['control'] for p in pairs)[47],median_reduction=1-medians['candidate']/medians['control'])
            finally:
                for shell in shells.values():shell.close()
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:{n:v for n,v in s.items() if n!='pairs'} for k,s in summary.items()},indent=2))
else:raise SystemExit('correctness or measure')
