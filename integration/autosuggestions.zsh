# Wsh autosuggestions adapter.

typeset -g WSH_AUTOSUGGESTIONS_OWNER=disabled
typeset -gi WSH_AUTOSUGGESTIONS_REPLACED=0
typeset -gi _WSH_AUTOSUGGESTIONS_LOAD=0

_wsh_detect_autosuggestions() {
  builtin emulate -L zsh -o no_aliases

  [[ ${WSH_DISABLE_AUTOSUGGESTIONS:-0} == 1 ]] && return 0

  local source=
  local known_external=0
  local existing=0
  (( ${+functions[_zsh_autosuggest_start]} || ${+functions[_zsh_autosuggest_bind_widgets]} )) && existing=1
  zle -l autosuggest-fetch >/dev/null 2>&1 && existing=1

  if (( existing )); then
    zmodload zsh/parameter 2>/dev/null || return 1
    source=${functions_source[_zsh_autosuggest_start]:-}
    if [[ -n $source && -f $source && -r $source ]]; then
      zmodload zsh/stat 2>/dev/null || true
      local -A source_stat=()
      if zstat -H source_stat -- $source 2>/dev/null && (( source_stat[size] == 27017 )); then
        zmodload zsh/system 2>/dev/null || return 1
        local candidate_content upstream_content
        local candidate_fd upstream_fd
        local candidate_count=0 upstream_count=0
        sysopen -r -o cloexec -u candidate_fd $source || return 1
        sysread -i $candidate_fd -s 27017 -c candidate_count candidate_content || true
        exec {candidate_fd}<&-
        sysopen -r -o cloexec -u upstream_fd ${WSH_BUNDLE_ROOT}/share/wsh/defaults/zsh-autosuggestions.zsh || return 1
        sysread -i $upstream_fd -s 27017 -c upstream_count upstream_content || true
        exec {upstream_fd}<&-
        (( candidate_count == 27017 && upstream_count == 27017 )) && [[ $candidate_content == $upstream_content ]] && known_external=1
      fi
    fi

    if (( ! known_external )); then
      WSH_AUTOSUGGESTIONS_OWNER=external-unknown
      return 0
    fi

    if (( ${#_ZSH_AUTOSUGGEST_BIND_COUNTS} )) || [[ -n ${_ZSH_AUTOSUGGEST_ASYNC_FD:-} || -n ${_ZSH_AUTOSUGGEST_CHILD_PID:-} ]]; then
      WSH_AUTOSUGGESTIONS_OWNER=external-active
      return 0
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
  source ${WSH_BUNDLE_ROOT}/share/wsh/defaults/zsh-autosuggestions.zsh
  [[ ${WSH_AUTOSUGGEST_ASYNC:-1} == 0 ]] && unset ZSH_AUTOSUGGEST_USE_ASYNC
  WSH_AUTOSUGGESTIONS_OWNER=wsh
fi
unset _WSH_AUTOSUGGESTIONS_LOAD
