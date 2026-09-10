#!/usr/bin/env python3
"""Observe composed regions at the redraw boundary, before ZLE changes temporary regions."""
import hashlib
import json
import os
from pathlib import Path
import pty
import select
import signal
import statistics
import sys
import time
binary,fixture,out=[Path(p).resolve() for p in sys.argv[1:4]];mode=sys.argv[4]
out.mkdir(parents=True,exist_ok=True)
workloads={'short':'echo hello','repeated':'echo hello; '*100,'distinct':''.join(f'wsh_probe_{i} hello; ' for i in range(100)), 'multiline':'if true; then\n echo "${HOME}"\nfi'}
config=r'''
PROMPT='HIGHLIGHT> '
ZSH_HIGHLIGHT_HIGHLIGHTERS=(main brackets)
source $WSH_TEST_SOURCE
for ((i=0;i<100;i++)); do functions[wsh_probe_$i]=':'; done
_clear() { BUFFER='' POSTDISPLAY='' CURSOR=0; }
zle -N _clear
bindkey '^G' _clear
typeset -ga _wsh_observed_regions
_report_redraw() {
 [[ $WSH_TEST_CAPTURE == 1 ]] && _wsh_observed_regions=("${region_highlight[@]}")
 print -nr -- $'\e]777;redraw;'"$#BUFFER"$'\a'
}
_inspect() { [[ $WSH_TEST_CAPTURE == 0 ]] && _wsh_observed_regions=("${region_highlight[@]}"); print -nr -- $'\e]777;regions;'"${(j:;:)_wsh_observed_regions}"$'\a'; }
zle -N _inspect
bindkey '^T' _inspect
autoload -Uz add-zle-hook-widget
_install_redraw() {
 add-zle-hook-widget line-pre-redraw _zsh_highlight__zle-line-pre-redraw
 add-zle-hook-widget line-finish _zsh_highlight__zle-line-finish
 add-zle-hook-widget line-pre-redraw _report_redraw
 add-zsh-hook -d precmd _install_redraw
}
autoload -Uz add-zsh-hook
add-zsh-hook precmd _install_redraw
'''
class Shell:
 def __init__(self,owner):
  self.output=bytearray();home=out/owner;home.mkdir(exist_ok=True);(home/'.zshrc').write_text(config)
  env=dict(PATH='/usr/bin:/bin',HOME=str(home),ZDOTDIR=str(home),TERM='xterm-256color',LC_ALL='C.UTF-8',WSH_THEME='',WSH_TEST_CAPTURE='0' if '--capture-overhead' in sys.argv and owner=='control' else '1',WSH_TEST_MEASURE='1' if mode=='measure' else '0',WSH_DISABLE_SYNTAX_HIGHLIGHTING='1',WSH_TEST_SOURCE=str(fixture/owner/'zsh-syntax-highlighting.zsh'))
  env.update({k:v for k,v in os.environ.items() if k.endswith('SAN_OPTIONS')})
  self.pid,self.fd=pty.fork()
  if not self.pid:
   os.chdir(home);os.sched_setaffinity(0,{0});os.execve(binary,[str(binary),'-di'],env)
  self.wait(b'\x1b]133;B',0)
 def wait(self,marker,offset):
  end=time.monotonic()+10
  while marker not in self.output[offset:]:
   assert time.monotonic()<end,bytes(self.output[-1000:])
   if select.select([self.fd],[],[],.05)[0]:self.output.extend(os.read(self.fd,65536))
 def frame(self,buffer,offset):
  self.wait(b'\x1b]777;redraw;'+str(len(buffer)).encode()+b'\x07',offset)
  return ''
 def redraw(self,buffer):
  offset=len(self.output);os.write(self.fd,b'\x07');self.frame('',offset)
  offset=len(self.output);start=time.monotonic_ns()
  os.write(self.fd,b'\x1b[200~'+buffer.encode()+b'\x1b[201~')
  regions=self.frame(buffer,offset)
  elapsed=(time.monotonic_ns()-start)/1e6
  offset=len(self.output);os.write(self.fd,b'\x14');marker=b'\x1b]777;regions;'
  self.wait(marker,offset);position=self.output.index(marker,offset)+len(marker)
  self.wait(b'\x07',position);end=self.output.index(b'\x07',position)
  regions=bytes(self.output[position:end]).decode()
  return elapsed,regions
 def close(self,owner):
  (out/(owner+'.pty')).write_bytes(self.output)
  try:os.kill(self.pid,signal.SIGHUP)
  except ProcessLookupError:pass
  os.waitpid(self.pid,0);os.close(self.fd)
identity=hashlib.sha256((fixture/'candidate/highlighters/main/main-highlighter.zsh').read_bytes()).hexdigest()
selected=workloads
if mode=='measure':
 previous=json.loads((out/'correctness.json').read_text());assert previous['fixture_sha256']==identity
 selected={k:v for k,v in workloads.items() if previous['workloads'][k]['equal']}
shells={o:Shell(o) for o in ('control','candidate')};results={}
try:
 for name,buffer in selected.items():
  pairs=[];regions={}
  for i in range(50 if mode=='measure' else 1):
   pair={}
   for owner in (('control','candidate') if i%2==0 else ('candidate','control')):
    pair[owner],regions[owner]=shells[owner].redraw(buffer)
   if mode=='measure':assert regions['control']==regions['candidate'],(name,regions)
   pairs.append(pair)
  medians={o:statistics.median(p[o] for p in pairs) for o in shells}
  results[name]=dict(equal=bool(regions['control']) and regions['control']==regions['candidate'],regions=regions,pairs=pairs,median_ms=medians,
                     median_reduction=1-medians['candidate']/medians['control'],paired_p95_delta_ms=sorted(p['candidate']-p['control'] for p in pairs)[47 if mode=='measure' else 0])
finally:
 for owner,shell in shells.items():shell.close(owner)
(out/(mode+'.json')).write_text(json.dumps(dict(fixture_sha256=identity,workloads=results),indent=2)+'\n')
print(json.dumps({name:{k:v for k,v in data.items() if k not in ('regions','pairs')} for name,data in results.items()},indent=2))
