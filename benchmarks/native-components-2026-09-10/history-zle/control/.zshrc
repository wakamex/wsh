
PROMPT='HISTORY> '
module_path=($WSH_TEST_MODULE $module_path)
zmodload wshhistory
source $WSH_TEST_SOURCE
HISTSIZE=30000
unsetopt hist_ignore_all_dups hist_ignore_dups
HISTORY_SUBSTRING_SEARCH_ENSURE_UNIQUE=$WSH_TEST_UNIQUE
HISTORY_SUBSTRING_SEARCH_FUZZY=$WSH_TEST_FUZZY
HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_TIMEOUT=0
[[ $WSH_TEST_VI == 1 ]] && bindkey -v
bindkey '^P' history-substring-search-up
bindkey '^N' history-substring-search-down
for ((i=0;i<WSH_TEST_COUNT;i++)); do print -s -- "echo duplicate $((i%3))"; done
print -s -- $'echo multiline\nsecond'
print -s -- 'echo é newest'
_custom() { BUFFER+=' CUSTOM'; CURSOR=$#BUFFER; }
zle -N _custom
bindkey '^X' _custom
_capture() {
  print -nr -- $'\x1eBUFFER:'"$BUFFER"$'\x1f'
  BUFFER='' POSTDISPLAY='' CURSOR=0
  _history_substring_search_result=''
  zle redisplay
}
zle -N _capture
bindkey '^G' _capture
