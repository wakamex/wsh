# Initialize completion when user startup files did not, then apply queued compdef calls.
if [[ ${functions[compdef]-} == *_wsh_compdef_queue* ]]; then
  unfunction compdef
  if [[ ${WSH_DISABLE_COMPLETION:-0} != 1 ]]; then
    autoload -Uz compinit
    # -i skips completion files in directories other users can write to.
    compinit -i
  fi
fi
if (( ${+functions[compdef]} )); then
  () {
    local call
    for call in $_wsh_compdef_queue; do eval "compdef $call"; done
  }
fi
unset _wsh_compdef_queue
# Colours for ls and completion lists when the login files set none.
if (( ! ${+LS_COLORS} )) && [[ -x /usr/bin/dircolors ]]; then
  eval "$(/usr/bin/dircolors -b)"
fi
