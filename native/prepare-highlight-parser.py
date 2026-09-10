#!/usr/bin/env python3
"""Replace the main command-list parser in a private upstream test checkout."""
from pathlib import Path
import shutil
import sys
root=Path(__file__).resolve().parents[1]
upstream,module,out=map(Path,sys.argv[1:])
for owner in ('control','candidate'):
 target=out/owner
 shutil.copytree(upstream,target,ignore=shutil.ignore_patterns('.git'))
 shutil.copytree(root/'third_party/zsh-syntax-highlighting',target,dirs_exist_ok=True)
 if owner=='candidate':
  p=target/'highlighters/main/main-highlighter.zsh';s=p.read_text()
  a=s.index('_zsh_highlight_main_highlighter_highlight_list()');b=s.index('\n# Check if $arg is variable assignment',a)
  s=s[:a]+'''_zsh_highlight_main_highlighter_highlight_list() {
  local arg buf=$4 this_word highlight_glob=true alias_style param_style style
  local -a in_alias list_highlights match mbegin mend _wsh_highlight_words
  local _wsh_highlight_input
  integer in_param=0 buf_offset=$1 start_pos=0 end_pos=0 has_end=$3
  builtin wsh-highlight-list "$@"
}
'''+s[b:]
  p.write_text('module_path=('+str(module)+' $module_path)\nzmodload wshhighlightparser || return 2\n'+s)
