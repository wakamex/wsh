# Public configuration and ZLE registration for the native history owner.
: ${HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_FOUND='bg=magenta,fg=white,bold'}
: ${HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_NOT_FOUND='bg=red,fg=white,bold'}
: ${HISTORY_SUBSTRING_SEARCH_GLOBBING_FLAGS='i'}
: ${HISTORY_SUBSTRING_SEARCH_ENSURE_UNIQUE=''}
: ${HISTORY_SUBSTRING_SEARCH_FUZZY=''}
: ${HISTORY_SUBSTRING_SEARCH_PREFIXED=''}
history-substring-search-up() { builtin wsh-history up }
history-substring-search-down() { builtin wsh-history down }
zle -N history-substring-search-up
zle -N history-substring-search-down

# Preserve the pinned plugin's highlighter ordering and standalone cleanup.
if (( ! $+functions[_zsh_highlight] )); then
  _zsh_highlight() {
    [[ $KEYS == [[:print:]] ]] && region_highlight=()
    return 0
  }
  _history-substring-search-zle-line-finish() {
    () { local -h -r WIDGET=zle-line-finish; _zsh_highlight }
  }
  _history-substring-search-zle-line-pre-redraw() {
    if (( $+ZSH_HIGHLIGHT_VERSION )); then
      add-zle-hook-widget -d zle-line-pre-redraw _history-substring-search-zle-line-pre-redraw
      add-zle-hook-widget -d zle-line-finish _history-substring-search-zle-line-finish
      return 0
    fi
    true && _zsh_highlight "$@"
  }
  autoload -Uz add-zle-hook-widget
  if [[ -o zle ]]; then
    add-zle-hook-widget zle-line-pre-redraw _history-substring-search-zle-line-pre-redraw
    add-zle-hook-widget zle-line-finish _history-substring-search-zle-line-finish
  fi
fi
