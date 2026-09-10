# Remove only recognized git-prompt hooks after Wsh takes prompt ownership.
typeset -g WSH_GIT_PROMPT_OWNER=absent


_wsh_git_prompt_takeover() {
  builtin emulate -L zsh -o no_aliases
  (( ${+functions[update_current_git_vars]} )) || return 0
  WSH_GIT_PROMPT_OWNER=external
  [[ $WSH_PROMPT_OWNER == wsh ]] || return 0
  WSH_GIT_PROMPT_OWNER=external-unknown
  zmodload zsh/parameter || return 0
  local source=${functions_source[update_current_git_vars]:-}
  local reference=$WSH_BUNDLE_ROOT/share/wsh/defaults/oh-my-zsh-git-prompt
  local function_name
  for function_name in chpwd_update_git_vars preexec_update_git_vars precmd_update_git_vars git_super_status; do
    [[ -n $source && ${functions_source[$function_name]:-} == $source ]] || return 0
  done
  [[ ${__GIT_PROMPT_DIR:-} == ${source:h} ]] || return 0
  _wsh_plugin_recognized git-prompt $source $__GIT_PROMPT_DIR/gitstatus.py || return 0
  autoload -Uz add-zsh-hook
  add-zsh-hook -d chpwd chpwd_update_git_vars
  add-zsh-hook -d precmd precmd_update_git_vars
  add-zsh-hook -d preexec preexec_update_git_vars
  WSH_GIT_PROMPT_OWNER=wsh
}
_wsh_git_prompt_takeover
unfunction _wsh_git_prompt_takeover
