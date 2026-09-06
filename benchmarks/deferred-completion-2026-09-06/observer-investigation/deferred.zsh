# Experimental first-Tab adapter, sourced only by private benchmark fixtures.
if (( ! $+functions[compdef] && ! $+parameters[_comps] )); then
  if [[ $(bindkey '^I') == '"^I" expand-or-complete' ]]; then
    _deferred_tab() {
      autoload -Uz compinit
      compinit -i -d "$HOME/.zcompdump" || return
      (( ++_DEFERRED_RUNS ))
      if [[ $WSH_DIRECTORY_JUMP_OWNER == wsh ]]; then
        compdef _zshz zshz "${ZSHZ_CMD:-${_Z_CMD:-z}}"
      fi
      bindkey '^I' expand-or-complete
      if [[ $WSH_AUTOSUGGESTIONS_OWNER == wsh ]]; then
        _zsh_autosuggest_bind_widgets
      fi
      zle expand-or-complete
    }
    zle -N _deferred_tab
    bindkey '^I' _deferred_tab
  fi
fi
