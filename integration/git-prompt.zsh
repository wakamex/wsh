# Remove only recognized git-prompt hooks after Wsh takes prompt ownership.
typeset -g WSH_GIT_PROMPT_OWNER=absent
_wsh_git_prompt_files_equal() {
  builtin emulate -L zsh -o no_aliases
  zmodload zsh/stat zsh/system 2>/dev/null || return 1
  local candidate bundled candidate_content bundled_content
  local candidate_fd bundled_fd
  local candidate_count bundled_count
  while (( $# )); do
    candidate=$1
    bundled=$2
    shift 2
    [[ -f $candidate && -r $candidate && -f $bundled && -r $bundled ]] || return 1

    local -A candidate_stat=() bundled_stat=()
    zstat -H candidate_stat -- $candidate 2>/dev/null || return 1
    zstat -H bundled_stat -- $bundled 2>/dev/null || return 1
    (( candidate_stat[size] == bundled_stat[size] && candidate_stat[size] <= 131072 )) || return 1

    candidate_count=0
    bundled_count=0
    sysopen -r -o cloexec -u candidate_fd $candidate || return 1
    sysread -i $candidate_fd -s $candidate_stat[size] -c candidate_count candidate_content || true
    exec {candidate_fd}<&-
    sysopen -r -o cloexec -u bundled_fd $bundled || return 1
    sysread -i $bundled_fd -s $bundled_stat[size] -c bundled_count bundled_content || true
    exec {bundled_fd}<&-
    (( candidate_count == candidate_stat[size] && bundled_count == bundled_stat[size] )) && [[ $candidate_content == $bundled_content ]] || return 1
  done
}


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
  _wsh_git_prompt_files_equal $source $reference/git-prompt.plugin.zsh \
    $__GIT_PROMPT_DIR/gitstatus.py $reference/gitstatus.py || return 0
  autoload -Uz add-zsh-hook
  add-zsh-hook -d chpwd chpwd_update_git_vars
  add-zsh-hook -d precmd precmd_update_git_vars
  add-zsh-hook -d preexec preexec_update_git_vars
  WSH_GIT_PROMPT_OWNER=wsh
}
_wsh_git_prompt_takeover
unfunction _wsh_git_prompt_takeover _wsh_git_prompt_files_equal
