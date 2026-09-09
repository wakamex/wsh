#!/usr/bin/env python3
"""Compare full registration against real compinit, including hostile headers."""
import json
import os
from pathlib import Path
import subprocess
import sys

bundle,proto,out=[Path(p).resolve() for p in sys.argv[1:]]
out.mkdir(parents=True,exist_ok=True)
home=out/'home';home.mkdir();first=home/'first [x]';first.mkdir();second=home/'second';second.mkdir()
headers=[b'#compdef probe\n',b'#compdef -p probe*\n',b'#compdef -P other*\n',b'#compdef -k complete-word ^Xq\n',b'#compdef -K probe-widget complete-word ^Xw\n',b'#autoload -U\n',b'#autoload\n',b'#compdef probe=git\n',b'#compdef "quoted name" $(false)\n',b'#compdef probe\t \n',b'#compdef \xc3\xa9cho\n',b'#compdef bad\x00value\n',b'#compdef '+b'x'*5000+b'\n',b'#compdef no-newline',b'\n',b'#autoload +X\n']
for i,data in enumerate(headers):(first/f'_probe{i}').write_bytes(data)
for name in ('_skip;name','_skip|name','_skip&name','_skip~','_skip.zwc','ordinary'):(first/name).write_text('#compdef MUST_NOT_REGISTER\n')
(second/'_probe0').write_text('#compdef MUST_NOT_SHADOW\n')
(first/'_git').write_text('#compdef CUSTOM_GIT_PRIORITY\n')
script=out/'compare.zsh'
script.write_text('''fpath=($HOME/'first [x]' $HOME/second $1)
if [[ $2 == candidate ]]; then functions[compinit]="$(< $3)"; else autoload -Uz compinit; fi
if [[ $4 == refuse ]]; then compinit -D < /dev/null; else compinit -i -D; fi
print -r -- "STATUS:$?"
typeset -p _comps _services _patcomps _postpatcomps _compautos
zle -l
''')
rows=[]
for security in ('secure','insecure','refuse'):
 first.chmod(0o755 if security=='secure' else 0o777)
 variants=[]
 for owner in ('control','candidate'):
  result=subprocess.run([bundle/'bin/wsh','-df',script,next((bundle/'share/zsh').glob('*/functions')),owner,proto/'compinit',security],env=dict(os.environ,PATH='/usr/bin:/bin',HOME=str(home),LC_ALL='C.UTF-8'),capture_output=True,timeout=10)
  # Function-name prefixes in diagnostics identify the reader being tested.
  stderr=result.stderr.decode(errors='backslashreplace').replace('_wsh_completion_autoload:autoload:','compinit:autoload:')
  variants.append(dict(status=result.returncode,stdout=sorted(result.stdout.decode(errors='backslashreplace').splitlines()),stderr=stderr))
 rows.append(dict(security=security,variants=variants,equal=variants[0]==variants[1]))
(out/'results.json').write_text(json.dumps(rows,indent=2)+'\n');first.chmod(0o755)
assert all(r['equal'] for r in rows), [r['security'] for r in rows if not r['equal']]
print('PASS: real compinit custom/hostile headers, duplicate priority and security refusal')
