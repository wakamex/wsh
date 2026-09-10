#!/usr/bin/env python3
"""Compare removal suppression and re-entry using the actual retained prompt hooks."""
import json
import os
from pathlib import Path
import subprocess
import sys

binary, module, fixture, out = [Path(p).resolve() for p in sys.argv[1:]]
out.mkdir(parents=True, exist_ok=True)
home = out/'home'
project = home/'project'
project.mkdir(parents=True, exist_ok=True)
other = home/'other'
other.mkdir(exist_ok=True)
script = out/'run.zsh'
script.write_text('''module_path=($1 $module_path)
(( $+builtins[wsh-directory] )) || zmodload wshdirectory || exit 90
source "$2"
cd "$HOME/project"
zshz -x "$PWD" || exit 1
if [[ $3 == reenter ]]; then
  cd "$HOME/other"
  cd "$HOME/project"
elif [[ $3 == reload ]]; then
  zsh-z_plugin_unload || exit 2
  source "$2"
fi
_zshz_precmd
''')
rows = []
for mode in ('stay', 'reenter', 'reload'):
    variants = []
    for owner in ('control','candidate'):
        (home/'db').write_text(str(project)+'|2|1700000000\n')
        result = subprocess.run([binary,'-df',script,module,fixture/(owner+'.zsh'),mode], env=dict(os.environ, HOME=str(home), ZSHZ_DATA=str(home/'db'), WSH_QUERY_NOW='1800000000', LC_ALL='C.UTF-8'), capture_output=True, timeout=10)
        # communicate waits for the actual disowned writer to close its inherited pipes.
        variants.append(dict(status=result.returncode, stdout=result.stdout.hex(), stderr=result.stderr.hex(), database=(home/'db').read_bytes().hex()))
    rows.append(dict(mode=mode, variants=variants, equal=variants[0]==variants[1]))
(out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
assert all(row['equal'] and all(v['status'] == 0 and not v['stderr'] for v in row['variants']) for row in rows)

extra = out/'custom-unload.zsh'
extra.write_text('''module_path=($1 $module_path)
(( $+builtins[wsh-directory] )) || zmodload wshdirectory || exit 90
ZSHZ_CMD=jump
source "$2"
_custom_cd() { print -r -- "CUSTOM:$1"; builtin cd "$1" }
ZSHZ_CD=_custom_cd
zshz project || exit 1
[[ $PWD == "$HOME/project" ]] || exit 2
zsh-z_plugin_unload || exit 3
(( ! $+aliases[jump] && ! $+functions[zshz] )) || exit 4
(( ${#${(M)chpwd_functions:#_zshz_chpwd}} == 0 )) || exit 5
(( ${#${(M)precmd_functions:#_zshz_precmd}} == 0 )) || exit 6
print UNLOADED
''')
variants=[]
for owner in ('control','candidate'):
    (home/'db').write_text(str(project)+'|2|1700000000\n')
    result=subprocess.run([binary,'-df',extra,module,fixture/(owner+'.zsh')],env=dict(os.environ,HOME=str(home),ZSHZ_DATA=str(home/'db'),WSH_QUERY_NOW='1800000000',LC_ALL='C.UTF-8'),capture_output=True,timeout=10)
    variants.append(dict(status=result.returncode,stdout=result.stdout.hex(),stderr=result.stderr.hex()))
(out/'custom-unload.json').write_text(json.dumps(variants,indent=2)+'\n')
assert variants[0]==variants[1] and all(v['status']==0 and not v['stderr'] for v in variants),variants
print('PASS: custom cd and actual plugin unload')
