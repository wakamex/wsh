#!/usr/bin/env python3
"""Compare actual completion widgets using the pinned completion definition."""
import importlib.util
import json
import os
from pathlib import Path
import pty
import sys

root = Path(__file__).resolve().parents[1]
binary, module, fixture, out = [Path(p).resolve() for p in sys.argv[1:]]
out.mkdir(parents=True, exist_ok=True)
(out/'transcripts').mkdir(exist_ok=True)
completion_fixture=out/'functions'
completion_fixture.mkdir(exist_ok=True)
for owner in ('control','candidate'):
    (completion_fixture/(owner+'.zsh')).write_bytes((fixture/(owner+'.zsh')).read_bytes())
(completion_fixture/'_zshz').write_bytes((root/'third_party/zsh-z/_z').read_bytes())
fixture=completion_fixture
spec = importlib.util.spec_from_file_location('pty_fixture',root/'benchmarks/deferred-completion-2026-09-06/run.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.OUT = out
config = '''PROMPT='DIRECTORY> '
module_path=($WSH_TEST_MODULE $module_path)
zmodload wshdirectory
autoload -Uz compinit
compinit -i -D
ZSHZ_DATA=$HOME/db
source $WSH_TEST_SOURCE
_capture() {
  print -nr -- $'\\x1eBUFFER:'"$BUFFER"$'\\x1f'
  BUFFER='' POSTDISPLAY='' CURSOR=0
  zle redisplay
}
zle -N _capture
bindkey '^G' _capture
'''
class Shell(base.Shell):
    def __init__(self, owner):
        self.label=owner
        self.output=bytearray()
        home=out/'home'
        home.mkdir(exist_ok=True)
        for name in ('needle', 'project space'):
            (home/name).mkdir(exist_ok=True)
        (home/'db').write_text(''.join(str(home/name)+'|2|1700000000\n' for name in ('needle','project space')))
        (home/'.zshrc').write_text(config)
        env=dict(PATH='/usr/bin:/bin',HOME=str(home),ZDOTDIR=str(home),TERM='xterm-256color',LC_ALL='C.UTF-8',WSH_THEME='',WSH_DISABLE_DIRECTORY_JUMP='1',WSH_DISABLE_HISTORY_SUBSTRING_SEARCH='1',WSH_DISABLE_AUTOSUGGESTIONS='1',WSH_TEST_MODULE=str(module),WSH_TEST_SOURCE=str(fixture/(owner+'.zsh')))
        env.update({k:v for k,v in os.environ.items() if k.endswith('SAN_OPTIONS')})
        self.pid,self.fd=pty.fork()
        if self.pid==0:
            os.chdir(home)
            os.execve(binary,[str(binary),'-di'],env)
        self.wait(base.READY)
variants=[]
for owner in ('control','candidate'):
    shell=Shell(owner)
    try:
        variants.append([shell.capture(keys)[0] for keys in (b'z needle\t',b'z project\t',b'z -r needle\t')])
    finally:
        shell.close()
(out/'results.json').write_text(json.dumps(variants,indent=2)+'\n')
assert variants[0]==variants[1],variants
assert all('/' in value for value in variants[0]),variants
print('PASS: three paired actual directory completion cases')
