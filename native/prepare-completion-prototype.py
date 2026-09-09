#!/usr/bin/env python3
"""Prepare a readonly-dump compinit experiment from the pinned real function."""
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

bundle=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir(parents=True)
source=next((bundle/'share/zsh').glob('*/functions/compinit'));original=source.read_text()
text=original.replace(' C d:: D i u w || return',' C d:: D i u w R || return').replace('  if [[ $_i_autodump = 1 ]]; then','  if [[ $_i_autodump = 1 && ! -v "_i_opth[-R]" ]]; then')
assert text!=original and text.count('_i_opth[-R]')==1
text='# Wsh prototype: -R reads the selected dump but never writes it.\n'+text
if '--bulk' in sys.argv[3:]:
    text=text.replace('  typeset -A _i_test', "  typeset -A _i_test\n  typeset _i_bulk _i_fd _i_header\n  zmodload -F zsh/system b:sysread 2>/dev/null && _i_bulk=yes")
    old="      IFS=$' \t' read -rA _i_line < $_i_file"
    # The source spells the tab as a backslash escape.
    old=old.replace('\t', r'\t')
    assert text.count(old)==1,repr(old)
    text=text.replace(old, r'''      if [[ $_i_bulk == yes ]] && { exec {_i_fd}< $_i_file } 2>/dev/null; then
        _i_header=''
        builtin sysread -i $_i_fd -s 4096 _i_header 2>/dev/null
        exec {_i_fd}<&-
        if [[ $_i_header == *$'\n'* ]]; then
          _i_header=${_i_header%%$'\n'*}
          _i_line=( ${(s: :)${_i_header//$'\t'/ }} )
          [[ -z $_i_header || $_i_header == *' ' || $_i_header == *$'\t' ]] && _i_line+=('')
        else
          IFS=$' \t' read -rA _i_line < $_i_file
        fi
      else
        IFS=$' \t' read -rA _i_line < $_i_file
      fi''')
(out/'compinit').write_text(text)
(out/'readonly.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='a/Completion/compinit',tofile='b/Completion/compinit')))
functions=source.parent
script='fpath=($1); autoload -Uz compinit; compinit -i -d "$2"'
subprocess.run([bundle/'bin/wsh','-dfc',script,'seed',functions,out/'seed'],env=dict(PATH='/usr/bin:/bin',HOME=str(out),LC_ALL='C.UTF-8'),check=True)
(out/'metadata.json').write_text(json.dumps(dict(bundle=str(bundle),source=str(source),source_sha256=hashlib.sha256(original.encode()).hexdigest(),candidate_sha256=hashlib.sha256(text.encode()).hexdigest(),seed_sha256=hashlib.sha256((out/'seed').read_bytes()).hexdigest(),function_directory=str(functions),command=sys.argv),indent=2)+'\n')
print(out)
