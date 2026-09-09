
PROMPT='SUGGEST> '
module_path=($WSH_TEST_MODULE $module_path)
zmodload wshsuggest
source $WSH_TEST_SOURCE
HISTSIZE=30000
unsetopt hist_ignore_all_dups hist_ignore_dups
for ((i=0;i<WSH_TEST_COUNT;i++)); do print -s -- "echo older $i"; done
print -s -- 'echo value newest'
print -s -- 'echo é newest'
print -s -- 'other replacement'
[[ $WSH_TEST_MODE == sync ]] && unset ZSH_AUTOSUGGEST_USE_ASYNC
if [[ $WSH_TEST_MODE == completion ]]; then
 autoload -Uz compinit
 compinit -i -d $HOME/.zcompdump
 ZSH_AUTOSUGGEST_STRATEGY=(completion)
fi
if [[ $WSH_TEST_MODE == custom ]]; then
 _zsh_autosuggest_strategy_probe() { sleep .02; suggestion="$1 custom"; }
 ZSH_AUTOSUGGEST_STRATEGY=(probe)
fi
[[ $WSH_TEST_MODE == vi ]] && bindkey -v
_state() { print -nr -- $'\x1eSTATE:'"$POSTDISPLAY|$CURSOR|$BUFFER"$'\x1f'; }
_custom() { BUFFER+='CUSTOM'; CURSOR=$#BUFFER; }
_capture() {
 print -nr -- $'\x1eBUFFER:'"$BUFFER"$'\x1f'
 BUFFER='' POSTDISPLAY='' CURSOR=0
 zle redisplay
}
zle -N _capture
zle -N _state
zle -N _custom
bindkey '^G' _capture
bindkey '^T' _state
bindkey '^X' _custom
bindkey '^D' autosuggest-disable
bindkey '^O' autosuggest-enable
bindkey '^F' autosuggest-accept
bindkey '^[f' forward-word
