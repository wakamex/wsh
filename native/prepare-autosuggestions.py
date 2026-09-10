#!/usr/bin/env python3
"""Generate the installed controller adapter from pinned upstream configuration."""
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
s=(root/'third_party/zsh-autosuggestions/zsh-autosuggestions.zsh').read_text()
(out/'control.zsh').write_text(s)
def function(name):
 a=s.index(name+'() {');b=s.index('\n}',a)+2
 return s[a:b]
config=s[:s.index('# Utility Functions')].rsplit('#--------------------------------------------------------------------#',1)[0]
completion='''_zsh_autosuggest_capture_postcompletion() { builtin wsh-autosuggest-service postcompletion; }
_zsh_autosuggest_capture_completion_widget() {
  local -a +h comppostfuncs=(_zsh_autosuggest_capture_postcompletion)
  builtin wsh-autosuggest-service capture
}
zle -N autosuggest-capture-completion _zsh_autosuggest_capture_completion_widget
_zsh_autosuggest_capture_completion_sync() {
  builtin wsh-autosuggest-service completion-setup
  zle autosuggest-capture-completion
}
_zsh_autosuggest_capture_completion_async() {
  builtin wsh-autosuggest-service completion-setup
  autoload +X _complete
  functions[_original_complete]=$functions[_complete]
  _complete() { unset 'compstate[vared]'; _original_complete "$@"; }
  vared 1
}
'''
parts=[config,completion,function('_zsh_autosuggest_invoke_original_widget')]
parts.append('''_zsh_autosuggest_strategy_completion() {
  emulate -L zsh
  setopt extendedglob
  local line REPLY
  builtin wsh-autosuggest-service completion "$1"
}''')
parts.append('_zsh_autosuggest_bind_widgets() { builtin wsh-autosuggest-service bind; }')
parts.append('_zsh_autosuggest_fetch() { builtin wsh-autosuggest-service fetch; }')
parts.append('_zsh_autosuggest_async_response() { builtin wsh-autosuggest-service response "$@"; }')
parts.append('_zsh_autosuggest_strategy_history() { builtin wsh-history-suggest "$1"; }')
for action in ('clear','fetch','suggest','accept','execute','enable','disable','toggle','modify','partial_accept'):
 parts.append('_zsh_autosuggest_widget_'+action+'() { builtin wsh-autosuggest-service widget '+action+' "$@"; }')
 if action not in ('modify','partial_accept'):parts.append('zle -N autosuggest-'+action+' _zsh_autosuggest_widget_'+action)
parts.append('''_zsh_autosuggest_start() {
  (( ${+ZSH_AUTOSUGGEST_MANUAL_REBIND} )) && add-zsh-hook -d precmd _zsh_autosuggest_start
  builtin wsh-autosuggest-service bind
}
typeset -g ZSH_AUTOSUGGEST_USE_ASYNC=
autoload -Uz add-zsh-hook
add-zsh-hook precmd _zsh_autosuggest_start
_wsh_autosuggest_complete_finish() { builtin wsh-autosuggest-service cancel; }
autoload -Uz add-zle-hook-widget
add-zle-hook-widget line-finish _wsh_autosuggest_complete_finish
add-zsh-hook zshexit _wsh_autosuggest_complete_finish
add-zsh-hook precmd _wsh_autosuggest_complete_finish
''')
(out/'candidate.zsh').write_text('\n'.join(parts))
