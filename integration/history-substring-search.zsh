# Wsh history substring search adapter.

typeset -g WSH_HISTORY_SUBSTRING_SEARCH_OWNER=disabled
typeset -gi WSH_HISTORY_SUBSTRING_SEARCH_REPLACED=0
typeset -gi _WSH_HISTORY_SUBSTRING_SEARCH_LOAD=0

_wsh_detect_history_substring_search() {
  builtin emulate -L zsh -o no_aliases

  [[ ${WSH_DISABLE_HISTORY_SUBSTRING_SEARCH:-0} == 1 ]] && return 0

  local up=history-substring-search-up
  local down=history-substring-search-down
  local source=
  local source_down=
  local known_external=0
  local existing=0
  (( ${+functions[$up]} || ${+functions[$down]} )) && existing=1
  zle -l $up >/dev/null 2>&1 && existing=1
  zle -l $down >/dev/null 2>&1 && existing=1

  if (( existing )); then
    zmodload zsh/parameter 2>/dev/null || return 1
    source=${functions_source[$up]:-}
    source_down=${functions_source[$down]:-}
    if [[ -n $source && $source == $source_down && -f $source && -r $source ]]; then
      _wsh_plugin_recognized history $source && known_external=1
    fi

    local function_name
    for function_name in ${(k)functions[(I)_history-substring-search-*]}; do
      [[ ${functions_source[$function_name]:-} == $source ]] || known_external=0
    done

    if (( ! known_external )); then
      WSH_HISTORY_SUBSTRING_SEARCH_OWNER=external-unknown
      return 0
    fi

    autoload -Uz add-zle-hook-widget
    add-zle-hook-widget -d zle-line-pre-redraw _history-substring-search-zle-line-pre-redraw 2>/dev/null || true
    add-zle-hook-widget -d zle-line-finish _history-substring-search-zle-line-finish 2>/dev/null || true
    if [[ ${functions_source[_zsh_highlight]:-} == $source ]]; then
      unfunction _zsh_highlight 2>/dev/null || true
    fi
    WSH_HISTORY_SUBSTRING_SEARCH_REPLACED=1
  fi

  _WSH_HISTORY_SUBSTRING_SEARCH_LOAD=1
}

_wsh_bind_history_substring_search() {
  builtin emulate -L zsh -o no_aliases
  zmodload zsh/terminfo 2>/dev/null || true

  local up=history-substring-search-up
  local down=history-substring-search-down
  local sequence binding widget replacement
  local -A desired_bindings=(${terminfo[kcuu1]:-$'\e[A'} $up ${terminfo[kcud1]:-$'\e[B'} $down)
  for sequence replacement in ${(kv)desired_bindings}; do
    binding=$(bindkey -M main $sequence 2>/dev/null) || binding=
    widget=${binding##* }
    case $widget in
      ''|undefined-key|up-line-or-history|down-line-or-history|up-history|down-history|up-line-or-beginning-search|down-line-or-beginning-search|history-substring-search-up|history-substring-search-down)
        bindkey -M main $sequence $replacement
        ;;
    esac
  done
}

_wsh_detect_history_substring_search
unfunction _wsh_detect_history_substring_search
if (( _WSH_HISTORY_SUBSTRING_SEARCH_LOAD )); then
  if [[ -r ${WSH_BUNDLE_ROOT}/share/wsh/defaults/native-history.zsh ]]; then
    source ${WSH_BUNDLE_ROOT}/share/wsh/defaults/native-history.zsh
  else
    source ${WSH_BUNDLE_ROOT}/share/wsh/defaults/zsh-history-substring-search.zsh
  fi
  WSH_HISTORY_SUBSTRING_SEARCH_OWNER=wsh
  _wsh_bind_history_substring_search
fi
unfunction _wsh_bind_history_substring_search
unset _WSH_HISTORY_SUBSTRING_SEARCH_LOAD
