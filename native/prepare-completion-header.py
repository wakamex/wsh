#!/usr/bin/env python3
"""Change only the first-line reader in the actual installed compinit."""
from pathlib import Path
import sys
bundle,module,out=[Path(p).resolve() for p in sys.argv[1:4]]
out.mkdir(parents=True,exist_ok=True)
s=next((bundle/'share/zsh').glob('*/functions/compinit')).read_text()
(out/'control').write_text(s)
old=r"      IFS=$' \t' read -rA _i_line < $_i_file"
assert s.count(old)==1
s=s.replace(old,'      wsh-completion-header "$_i_file" _i_line ||\n'+old)
(out/'compinit').write_text('module_path=('+str(module)+' $module_path)\nzmodload wshcompletion || return 2\n'+s)

if '--scan' in sys.argv[4:]:
    start=s.index('  for _i_dir in $fpath; do',s.index('if [[ -z "$_i_done" ]]'))
    end=s.index('  # If autodumping was requested',start)
    s=s[:start]+r"""  _wsh_completion_read() { IFS=$' \t' read -rA _i_line < "$1"; }
  _wsh_completion_autoload() { builtin autoload -rUz "$@"; }
  { wsh-completion-scan } always { unfunction _wsh_completion_read _wsh_completion_autoload }

"""+s[end:]
    (out/'compinit').write_text('module_path=('+str(module)+' $module_path)\nzmodload wshcompletion || return 2\n'+s)
