# Wsh autosuggestions adapter.

typeset -g WSH_AUTOSUGGESTIONS_OWNER=disabled
typeset -gi WSH_AUTOSUGGESTIONS_REPLACED=0
typeset -gi _WSH_AUTOSUGGESTIONS_LOAD=0

_wsh_detect_autosuggestions() {
  builtin emulate -L zsh -o no_aliases

  [[ ${WSH_DISABLE_AUTOSUGGESTIONS:-0} == 1 ]] && return 0

  local source=
  local handoff=
  local known_external=0
  local existing=0
  (( ${+functions[_zsh_autosuggest_start]} || ${+functions[_zsh_autosuggest_bind_widgets]} )) && existing=1
  zle -l autosuggest-fetch >/dev/null 2>&1 && existing=1

  if (( existing )); then
    zmodload zsh/parameter 2>/dev/null || return 1
    source=${functions_source[_zsh_autosuggest_start]:-}
    if [[ -n $source && -f $source && -r $source ]]; then
      if _wsh_plugin_recognized autosuggestions $source; then
        known_external=1
        handoff=$_WSH_PLUGIN_HANDOFF
      fi
    fi

    # Preserve runtime overrides of the implementation. Custom named strategies
    # remain supported, and generated wrappers retain their existing active owner.
    local function_name
    for function_name in ${(k)functions[(I)_zsh_autosuggest_*]}; do
      case $function_name in
        _zsh_autosuggest_bound_*|_zsh_autosuggest_orig_*) continue ;;
        _zsh_autosuggest_strategy_*)
          [[ $function_name == _zsh_autosuggest_strategy_(history|match_prev_cmd|completion) ]] || continue
          ;;
      esac
      [[ ${functions_source[$function_name]:-} == $source ]] || known_external=0
    done

    if (( ! known_external )); then
      WSH_AUTOSUGGESTIONS_OWNER=external-unknown
      return 0
    fi

    if (( ${#_ZSH_AUTOSUGGEST_BIND_COUNTS} )) || [[ -n ${_ZSH_AUTOSUGGEST_ASYNC_FD:-} || -n ${_ZSH_AUTOSUGGEST_CHILD_PID:-} ]]; then
      WSH_AUTOSUGGESTIONS_OWNER=external-active
      return 0
    fi

    # Before v0.6.0, upstream excluded zle-* inside its binder rather than
    # through the configurable ignore list. Preserve that implicit rule.
    if [[ $handoff == pending-widget-binding-legacy-zle-ignore || ${functions[_zsh_autosuggest_bind_widgets]:-} == *'zle-\*'* ]]; then
      ZSH_AUTOSUGGEST_IGNORE_WIDGETS+=('zle-*')
    fi

    autoload -Uz add-zsh-hook
    add-zsh-hook -d precmd _zsh_autosuggest_start 2>/dev/null || true
    WSH_AUTOSUGGESTIONS_REPLACED=1
  fi

  case ${WSH_AUTOSUGGEST_REBIND_MODE:-manual} in
    automatic)
      unset ZSH_AUTOSUGGEST_MANUAL_REBIND
      ;;
    *)
      (( ${+ZSH_AUTOSUGGEST_MANUAL_REBIND} )) || typeset -g ZSH_AUTOSUGGEST_MANUAL_REBIND=1
      ;;
  esac
  _WSH_AUTOSUGGESTIONS_LOAD=1
}

_wsh_detect_autosuggestions
unfunction _wsh_detect_autosuggestions
if (( _WSH_AUTOSUGGESTIONS_LOAD )); then
  source ${WSH_BUNDLE_ROOT}/share/wsh/defaults/native-autosuggestions.zsh
  [[ ${WSH_AUTOSUGGEST_ASYNC:-1} == 0 ]] && unset ZSH_AUTOSUGGEST_USE_ASYNC
  WSH_AUTOSUGGESTIONS_OWNER=wsh
fi
unset _WSH_AUTOSUGGESTIONS_LOAD
