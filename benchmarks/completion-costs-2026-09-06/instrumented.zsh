# Experimental first-Tab adapter, sourced only by private benchmark fixtures.
if (( ! $+functions[compdef] && ! $+parameters[_comps] )); then
  if [[ $(bindkey '^I') == '"^I" expand-or-complete' ]]; then
    _deferred_tab() {
      _COST_TIMES=($EPOCHREALTIME)
      autoload -Uz compinit
      _COST_TIMES+=($EPOCHREALTIME)
      compinit -i -d "$HOME/.zcompdump" || return
      _COST_TIMES+=($EPOCHREALTIME)
      (( ++_DEFERRED_RUNS ))
      if [[ $WSH_DIRECTORY_JUMP_OWNER == wsh ]]; then
        compdef _zshz zshz "${ZSHZ_CMD:-${_Z_CMD:-z}}"
      fi
      _COST_TIMES+=($EPOCHREALTIME)
      if [[ $WSH_DIRECTORY_JUMP_OWNER == wsh && ${ZSHZ[TAB_BINDING]:-} == _deferred_tab ]]; then
        ZSHZ[TAB_BINDING]=expand-or-complete
      fi
      [[ $(bindkey '^I') == '"^I" _deferred_tab' ]] && bindkey '^I' expand-or-complete
      _COST_TIMES+=($EPOCHREALTIME)
      if [[ $WSH_AUTOSUGGESTIONS_OWNER == wsh ]]; then
        _zsh_autosuggest_bind_widgets
      fi
      _COST_TIMES+=($EPOCHREALTIME)
      zle expand-or-complete
      _COST_TIMES+=($EPOCHREALTIME)
    }
    zle -N _deferred_tab
    bindkey '^I' _deferred_tab
  fi
fi
