# Wsh syntax-highlighting adapter.

typeset -g WSH_SYNTAX_HIGHLIGHTING_OWNER=disabled
typeset -gi _WSH_SYNTAX_HIGHLIGHTING_LOAD=0
typeset -gi _WSH_SYNTAX_HIGHLIGHTING_ACTIVATE_EXTERNAL=0


# Keep the external lifecycle and optional highlighters; upgrade only main.
_wsh_syntax_highlighting_native_main() {
  source ${WSH_BUNDLE_ROOT}/share/wsh/defaults/zsh-syntax-highlighting/highlighters/main/main-highlighter.zsh
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
    local main_source=${functions_source[_zsh_highlight_highlighter_main_paint]:-}
    local known_external=0 reference
    local -a active_highlighters=(${ZSH_HIGHLIGHT_HIGHLIGHTERS:-main})
    if (( ${active_highlighters[(Ie)main]} )) && [[ -n $main_source ]]; then
      if _wsh_plugin_recognized syntax $source $main_source ||
         _wsh_plugin_files_equal $source $bundled_root/zsh-syntax-highlighting.zsh $main_source $bundled_root/highlighters/main/main-highlighter.zsh; then
        known_external=1
      fi
      # Preserve main-parser functions overridden after loading an upstream file.
      local function_name
      for function_name in ${(k)functions[(I)_zsh_highlight_main_*]} _zsh_highlight_highlighter_main_predicate; do
        [[ ${functions_source[$function_name]:-} == $main_source ]] || known_external=0
      done
    fi

    if (( ! known_external )); then
      WSH_SYNTAX_HIGHLIGHTING_OWNER=external-unknown
      return 0
    fi

    # A custom optional highlighter may depend on the external installation.
    # Keep doctor from recommending removal of that installation.
    local external_owner=external-exact highlighter optional_source
    for highlighter in $active_highlighters; do
      [[ $highlighter == main ]] && continue
      optional_source=${functions_source[_zsh_highlight_highlighter_${highlighter}_paint]:-}
      if [[ $highlighter != (brackets|cursor|line|pattern|regexp) ]] ||
         ! _wsh_plugin_files_equal $optional_source $bundled_root/highlighters/$highlighter/${highlighter}-highlighter.zsh; then
        external_owner=external-unknown
      fi
    done

    local -a redraw_hooks=() finish_hooks=()
    zstyle -a zle-line-pre-redraw widgets redraw_hooks
    zstyle -a zle-line-finish widgets finish_hooks
    local -a redraw_matches=(${(M)redraw_hooks:#*:_zsh_highlight__zle-line-pre-redraw})
    local -a finish_matches=(${(M)finish_hooks:#*:_zsh_highlight__zle-line-finish})
    local redraw_count=$#redraw_matches
    local finish_count=$#finish_matches
    if (( redraw_count == 1 && finish_count == 1 )); then
      _wsh_syntax_highlighting_native_main
      WSH_SYNTAX_HIGHLIGHTING_OWNER=$external_owner
      return 0
    fi
    if (( redraw_count || finish_count )) || [[ ${widgets[self-insert]:-} == user:_zsh_highlight_widget_* ]]; then
      WSH_SYNTAX_HIGHLIGHTING_OWNER=external-unknown
      return 0
    fi

    _wsh_syntax_highlighting_native_main
    WSH_SYNTAX_HIGHLIGHTING_OWNER=$external_owner
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
unfunction _wsh_detect_syntax_highlighting _wsh_syntax_highlighting_native_main
