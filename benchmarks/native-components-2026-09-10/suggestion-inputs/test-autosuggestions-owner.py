#!/usr/bin/env python3
"""Exercise native editor actions with real ZLE, async history and completion."""
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
PROMPT='SUGGEST> '
module_path=($WSH_TEST_MODULE $module_path)
zmodload wshsuggest
source $WSH_TEST_SOURCE
HISTSIZE=30000
unsetopt hist_ignore_all_dups hist_ignore_dups
for ((i=0;i<WSH_TEST_COUNT;i++)); do print -s -- "echo older $i suffix"; done
print -s -- 'echo value newest'
print -s -- 'echo é newest'
print -s -- 'other replacement'
[[ $WSH_TEST_MODE == sync ]] && unset ZSH_AUTOSUGGEST_USE_ASYNC
if [[ $WSH_TEST_MODE == completion ]]; then
 autoload -Uz compinit
 compinit -i -d $HOME/.zcompdump
 ZSH_AUTOSUGGEST_STRATEGY=(completion)
fi
if [[ $WSH_TEST_MODE == custom ]]; then
 _zsh_autosuggest_strategy_probe() { print -r -- "$1" >> $HOME/requests; sleep .1; suggestion="$1 custom"; }
 ZSH_AUTOSUGGEST_STRATEGY=(probe)
fi
[[ $WSH_TEST_MODE == vi ]] && bindkey -v
_state() { print -nr -- $'\x1eSTATE:'"$POSTDISPLAY|$CURSOR|$BUFFER"$'\x1f'; }
_custom() { BUFFER+='CUSTOM'; CURSOR=$#BUFFER; }
_capture() {
 print -nr -- $'\x1eBUFFER:'"$BUFFER"$'\x1f'
 BUFFER='' POSTDISPLAY='' CURSOR=0
 zle redisplay
}
zle -N _capture
zle -N _state
zle -N _custom
bindkey '^G' _capture
bindkey '^T' _state
bindkey '^X' _custom
bindkey '^D' autosuggest-disable
bindkey '^O' autosuggest-enable
bindkey '^F' autosuggest-accept
bindkey '^[f' forward-word
'''
class Shell(base.Shell):
    def __init__(self,owner,label,mode='sync',count=100):
        self.label=label;self.output=bytearray();self.home=OUT/(owner+'-'+mode)
        self.home.mkdir(exist_ok=True);(self.home/'.zshrc').write_text(CONFIG)
        (self.home/'completion-unique-file').touch()
        env=dict(PATH='/usr/bin:/bin',HOME=str(self.home),ZDOTDIR=str(self.home),TERM='xterm-256color',LC_ALL='C.UTF-8',WSH_THEME='',WSH_DISABLE_DIRECTORY_JUMP='1',WSH_DISABLE_AUTOSUGGESTIONS='1',WSH_TEST_MODULE=str(MODULE),WSH_TEST_SOURCE=str(FIXTURE/f'{owner}.zsh'),WSH_TEST_MODE=mode,WSH_TEST_COUNT=str(count))
        env.update({k:v for k,v in os.environ.items() if k.endswith('SAN_OPTIONS')})
        self.pid,self.fd=pty.fork()
        if self.pid==0:
            os.chdir(self.home);os.sched_setaffinity(0,{0});os.execve(BINARY,[str(BINARY),'-di'],env)
        self.wait(base.READY)
        assert b'ERROR:' not in self.output, self.output
    def settled(self,keys,expected=None):
        offset=len(self.output);os.write(self.fd,keys)
        if expected is not None:self.wait(expected.encode(),offset)
        else:time.sleep(.06)
        return self.state()
if MODE=='correctness':
    rows=[]
    for mode in ('sync','async','vi','custom','completion'):
        variants=[]
        for owner in ('control','candidate'):
            shell=Shell(owner,f'{mode}-{owner}',mode)
            try:
                values=[]
                query=b'cat completion-' if mode=='completion' else b'echo v'
                expected='unique-file' if mode=='completion' else 'custom' if mode=='custom' else 'alue newest'
                values.append(shell.settled(query,expected))
                values.append(shell.capture(b'\x06')[0])
                if mode!='completion':
                    values.append(shell.settled('echo é'.encode(), 'custom' if mode=='custom' else 'newest'))
                    values.append(shell.capture(b'\x1bf')[0])
                    values.append(shell.settled(b'echo v\x15other', 'custom' if mode=='custom' else 'replacement'))
                    values.append(shell.capture(b'\x06')[0])
                if mode=='custom':
                    requests=shell.home/'requests';requests.write_text('')
                    os.write(shell.fd,b'pending old')
                    deadline=time.monotonic()+5
                    while 'pending old' not in requests.read_text():
                        assert time.monotonic()<deadline
                        time.sleep(.001)
                    values.append(shell.settled(b'\x15replacement', ' custom'))
                    values.append(shell.capture(b'\x06')[0])
                    time.sleep(.12)
                    assert shell.state()[0]=='', 'stale result after acceptance'
                values.append(shell.settled(b'echo v\x04'))
                values.append(shell.settled(b'\x0f', expected if mode!='completion' else None))
                values.append(shell.capture(b'\x18')[0])
                variants.append(values)
            finally:shell.close()
        rows.append(dict(mode=mode,variants=variants,equal=variants[0]==variants[1]))
        (OUT/'correctness.json').write_text(json.dumps(rows,indent=2)+'\n')
        assert rows[-1]['equal'], rows[-1]
    print('PASS: actual ZLE history, async, vi, custom/completion strategies and editor actions')
elif MODE=='measure':
    summary={}
    for count in (100,10000):
        shells={o:Shell(o,f'measure-{count}-{o}',count=count) for o in ('control','candidate')}
        try:
            pairs=[]
            for i in range(50):
                pair={};values={}
                for owner in (('control','candidate') if i%2==0 else ('candidate','control')):
                    # Both owners fetch synchronously; wait for the final edit before accepting.
                    shell=shells[owner];offset=len(shell.output);start=time.monotonic_ns()
                    os.write(shell.fd,b'echo older 0')
                    shell.wait(b'echo older 0',offset)
                    value,_=shell.capture(b'\x06');pair[owner]=(time.monotonic_ns()-start)/1e6;values[owner]=value
                assert values['control']==values['candidate']=='echo older 0 suffix',values
                pairs.append(pair)
            medians={o:statistics.median(p[o] for p in pairs) for o in shells}
            summary[str(count)]=dict(pairs=pairs,median_ms=medians,paired_p95_delta_ms=sorted(p['candidate']-p['control'] for p in pairs)[47],median_reduction=1-medians['candidate']/medians['control'])
        finally:
            for shell in shells.values():shell.close()
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:{n:v for n,v in s.items() if n!='pairs'} for k,s in summary.items()},indent=2))
else:raise SystemExit('correctness or measure')
