#!/usr/bin/env python3
"""Check readonly dump behavior against real compinit registrations and audit."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

BUNDLE,PROTO,OUT=[Path(x).resolve() for x in sys.argv[1:]];OUT.mkdir(parents=True)
functions=next((BUNDLE/'share/zsh').glob('*/functions'));rows=[]
script=OUT/'run.zsh';script.write_text('''fpath=($1)
[[ -d $HOME/extra ]] && fpath=($HOME/extra $fpath)
if [[ $2 == candidate ]]; then
  functions[compinit]="$(< $3)"
  compinit -i -R -d "$HOME/dump" || exit 2
else
  autoload -Uz compinit
  compinit -i -d "$HOME/dump" || exit 2
fi
typeset -p _comps _services _patcomps _postpatcomps _compautos
bindkey '^I'
''')
for case in ['valid','missing','stale-count','stale-version','directory','unreadable','custom','shadow','insecure']:
    observed={}; hashes={}
    for mode in ['control','candidate']:
        home=OUT/(case+'-'+mode);home.mkdir();dump=home/'dump'
        if case=='directory':dump.mkdir()
        elif case!='missing':
            data=(PROTO/'seed').read_bytes()
            if case=='stale-count':data=data.replace(b'#files: ',b'#files: 9',1)
            if case=='stale-version':data=data.replace(b'version: ',b'version: old-',1)
            dump.write_bytes(data)
            if case=='unreadable':dump.chmod(0)
        if case in ['custom','shadow','insecure']:
            extra=home/'extra';extra.mkdir()
            (extra/('_git' if case=='shadow' else '_wsh_custom')).write_text('#compdef wsh-custom\ncompadd custom\n')
            if case=='insecure':extra.chmod(0o777)
        before=hashlib.sha256(dump.read_bytes()).hexdigest() if dump.is_file() and case!='unreadable' else None
        result=subprocess.run([BUNDLE/'bin/wsh','-df',script,functions,mode,PROTO/'compinit'],env=dict(PATH='/usr/bin:/bin',HOME=str(home),LC_ALL='C.UTF-8'),capture_output=True,timeout=5)
        assert result.returncode==0,(case,mode,result.stdout,result.stderr)
        observed[mode]=sorted(result.stdout.decode().split())
        if case=='unreadable':dump.chmod(0o600)
        after=hashlib.sha256(dump.read_bytes()).hexdigest() if dump.is_file() else None
        if mode=='candidate':
            if case=='missing':assert not dump.exists()
            elif case=='unreadable':assert dump.read_bytes()==(PROTO/'seed').read_bytes()
            else:assert before==after
        hashes[mode]=dict(before=before,after=after,stderr=result.stderr.decode())
    passed=observed['control']==observed['candidate'];rows.append(dict(case=case,passed=passed,hashes=hashes));(OUT/'results.json').write_text(json.dumps(rows,indent=2)+'\n');assert passed,case
print('PASS: nine real compinit mapping, audit, invalidation and readonly-dump cases')
