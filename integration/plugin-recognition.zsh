_wsh_plugin_files_equal() {
  builtin emulate -L zsh -o no_aliases
  (( $# && $# % 2 == 0 )) || return 1
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

_wsh_plugin_recognized() {
  builtin emulate -L zsh -o no_aliases
  (( $# >= 2 )) || return 1
  typeset -g _WSH_PLUGIN_HANDOFF=
  local component=$1 row reference handoff
  shift
  local -a references pairs
  for row in "${(@f)_WSH_PLUGIN_REFERENCES[$component]}"; do
    references=("${(@s:|:)row}")
    handoff=$references[1]
    shift references
    (( $#references == $# )) || continue
    pairs=()
    local index=1
    for reference in $references; do
      pairs+=("${argv[$index]}" "$WSH_BUNDLE_ROOT/share/wsh/defaults/$reference")
      (( ++index ))
    done
    if _wsh_plugin_files_equal "${pairs[@]}"; then
      _WSH_PLUGIN_HANDOFF=$handoff
      return 0
    fi
  done
  _wsh_plugin_git_recognized "$component" "$@"
}
source "$WSH_BUNDLE_ROOT/share/wsh/defaults/plugin-catalog/catalog.zsh"
source "$WSH_BUNDLE_ROOT/share/wsh/defaults/plugin-git-provenance.zsh"
