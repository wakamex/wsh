# Wsh syntax-highlighting adapter.

typeset -g WSH_SYNTAX_HIGHLIGHTING_OWNER=disabled
typeset -gi _WSH_SYNTAX_HIGHLIGHTING_LOAD=0
typeset -gi _WSH_SYNTAX_HIGHLIGHTING_ACTIVATE_EXTERNAL=0

_wsh_syntax_files_equal() {
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

_wsh_detect_syntax_highlighting() {
  builtin emulate -L zsh -o no_aliases

  [[ ${WSH_DISABLE_SYNTAX_HIGHLIGHTING:-0} == 1 ]] && return 0

  if (( ${+ZSH_HIGHLIGHT_VERSION} )); then
    zmodload zsh/parameter zsh/zleparameter 2>/dev/null || {
      WSH_SYNTAX_HIGHLIGHTING_OWNER=external-unknown
      return 0
    }
    local source=${functions_source[_zsh_highlight]:-}
    local candidate_root=${source:h}
    local bundled_root=${WSH_BUNDLE_ROOT}/share/wsh/defaults/zsh-syntax-highlighting
    local known_external=1
    [[ $ZSH_HIGHLIGHT_VERSION == 0.8.1-dev ]] || known_external=0
    local -a compare_files=($source $bundled_root/zsh-syntax-highlighting.zsh)

    local -a active_highlighters=(${ZSH_HIGHLIGHT_HIGHLIGHTERS:-main})
    local highlighter function_name candidate
    for highlighter in $active_highlighters; do
      [[ $highlighter == (brackets|cursor|line|main|pattern|regexp) ]] || {
        known_external=0
        continue
      }
      function_name=_zsh_highlight_highlighter_${highlighter}_paint
      candidate=$candidate_root/highlighters/$highlighter/${highlighter}-highlighter.zsh
      (( ${+functions[$function_name]} )) || known_external=0
      [[ ${functions_source[$function_name]:-} == $candidate ]] || known_external=0
      compare_files+=($candidate $bundled_root/highlighters/$highlighter/${highlighter}-highlighter.zsh)
    done
    (( known_external )) && _wsh_syntax_files_equal $compare_files || known_external=0

    if (( ! known_external )); then
      WSH_SYNTAX_HIGHLIGHTING_OWNER=external-unknown
      return 0
    fi

    local -a redraw_hooks=() finish_hooks=()
    zstyle -a zle-line-pre-redraw widgets redraw_hooks
    zstyle -a zle-line-finish widgets finish_hooks
    local -a redraw_matches=(${(M)redraw_hooks:#*:_zsh_highlight__zle-line-pre-redraw})
    local -a finish_matches=(${(M)finish_hooks:#*:_zsh_highlight__zle-line-finish})
    local redraw_count=$#redraw_matches
    local finish_count=$#finish_matches
    if (( redraw_count == 1 && finish_count == 1 )); then
      WSH_SYNTAX_HIGHLIGHTING_OWNER=external-exact
      return 0
    fi
    if (( redraw_count || finish_count )) || [[ ${widgets[self-insert]:-} == user:_zsh_highlight_widget_* ]]; then
      WSH_SYNTAX_HIGHLIGHTING_OWNER=external-unknown
      return 0
    fi

    WSH_SYNTAX_HIGHLIGHTING_OWNER=external-exact
    _WSH_SYNTAX_HIGHLIGHTING_ACTIVATE_EXTERNAL=1
  else
    _WSH_SYNTAX_HIGHLIGHTING_LOAD=1
  fi

  autoload -Uz add-zsh-hook
  add-zsh-hook precmd _wsh_syntax_highlighting_start
}

_wsh_syntax_highlighting_start() {
  if (( _WSH_SYNTAX_HIGHLIGHTING_LOAD )); then
    source ${WSH_BUNDLE_ROOT}/share/wsh/defaults/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
    WSH_SYNTAX_HIGHLIGHTING_OWNER=wsh
  elif (( _WSH_SYNTAX_HIGHLIGHTING_ACTIVATE_EXTERNAL )); then
    autoload -Uz add-zle-hook-widget
    add-zle-hook-widget zle-line-pre-redraw _zsh_highlight__zle-line-pre-redraw
    add-zle-hook-widget zle-line-finish _zsh_highlight__zle-line-finish
  fi
  add-zsh-hook -d precmd _wsh_syntax_highlighting_start
  unset _WSH_SYNTAX_HIGHLIGHTING_LOAD _WSH_SYNTAX_HIGHLIGHTING_ACTIVATE_EXTERNAL
  unfunction _wsh_syntax_highlighting_start
}

_wsh_detect_syntax_highlighting
unfunction _wsh_detect_syntax_highlighting _wsh_syntax_files_equal
