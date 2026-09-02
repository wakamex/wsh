# wsh integration API 1

if [[ ! -o interactive || -n ${WSH_INTEGRATION_LOADED:-} ]]; then
  return 0
fi

typeset -gr WSH_INTEGRATION_LOADED=1
typeset -g WSH_RUNTIME_PID=''
typeset -g WSH_RUNTIME_INPUT_FD=''
typeset -g WSH_RUNTIME_OUTPUT_FD=''
typeset -g WSH_RUNTIME_READY=0

_wsh_runtime_stop() {
  emulate -L zsh
  if [[ -n $WSH_RUNTIME_INPUT_FD ]]; then
    print -r -u $WSH_RUNTIME_INPUT_FD -- '{"type":"shutdown","version":1,"id":0}' 2>/dev/null || true
    local stopped
    read -r -t 1 -u $WSH_RUNTIME_OUTPUT_FD stopped 2>/dev/null || true
    exec {WSH_RUNTIME_INPUT_FD}>&-
    WSH_RUNTIME_INPUT_FD=''
  fi
  if [[ -n $WSH_RUNTIME_OUTPUT_FD ]]; then
    exec {WSH_RUNTIME_OUTPUT_FD}<&-
    WSH_RUNTIME_OUTPUT_FD=''
  fi
  if [[ -n $WSH_RUNTIME_PID ]]; then
    wait $WSH_RUNTIME_PID 2>/dev/null || true
    WSH_RUNTIME_PID=''
  fi
  WSH_RUNTIME_READY=0
}

_wsh_runtime_start() {
  emulate -L zsh
  if [[ ! -x ${WSH_RUNTIME:-} || ! -f ${WSH_THEME:-} ]]; then
    print -u2 -- 'wsh: WSH_RUNTIME or WSH_THEME is unavailable'
    return 1
  fi

  coproc "$WSH_RUNTIME" serve --theme "$WSH_THEME"
  WSH_RUNTIME_PID=$!
  exec {WSH_RUNTIME_INPUT_FD}>&p
  exec {WSH_RUNTIME_OUTPUT_FD}<&p
  disown %%

  local ready
  if ! read -r -t 1 -u $WSH_RUNTIME_OUTPUT_FD ready; then
    print -u2 -- 'wsh: runtime did not become ready within 1 second'
    _wsh_runtime_stop
    return 1
  fi
  if [[ $ready != '{"version":1,"type":"ready","theme":'* ]]; then
    print -u2 -- "wsh: invalid runtime ready message: ${ready}"
    _wsh_runtime_stop
    return 1
  fi
  WSH_RUNTIME_READY=1
}

autoload -Uz add-zsh-hook
add-zsh-hook zshexit _wsh_runtime_stop
_wsh_runtime_start
