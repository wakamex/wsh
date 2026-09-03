# wsh integration API 1

if [[ ! -o interactive || -n ${WSH_INTEGRATION_LOADED:-} ]]; then
  return 0
fi

typeset -gr WSH_INTEGRATION_LOADED=1
typeset -g WSH_RUNTIME_PID=''
typeset -g WSH_RUNTIME_INPUT_FD=''
typeset -g WSH_RUNTIME_OUTPUT_FD=''
typeset -gi WSH_RUNTIME_READY=0
typeset -gi WSH_RUNTIME_GENERATION=0
typeset -gi WSH_RUNTIME_REQUEST_ID=0
typeset -gi WSH_RUNTIME_REPAINTS=0
typeset -gF WSH_COMMAND_STARTED_AT=0
typeset -gi WSH_RESET_TRANSIENT=0
typeset -g WSH_LAST_PROMPT='%# '
typeset -g WSH_LAST_RPROMPT=''

_wsh_hex_encode() {
  emulate -L zsh
  local LC_ALL=C value=$1 output='' byte
  local -i index
  for (( index = 1; index <= ${#value}; index++ )); do
    printf -v byte '%02x' "'${value[index]}"
    output+=$byte
  done
  REPLY=$output
}

_wsh_hex_decode() {
  emulate -L zsh
  setopt extendedglob
  local LC_ALL=C value=$1 escaped
  local -a match mbegin mend
  escaped=${value//(#b)(??)/\\x${match[1]}}
  printf -v REPLY '%b' "$escaped"
}

_wsh_runtime_disable_reader() {
  emulate -L zsh
  if [[ -n $WSH_RUNTIME_OUTPUT_FD ]]; then
    zle -F $WSH_RUNTIME_OUTPUT_FD 2>/dev/null || true
  fi
}

_wsh_runtime_stop() {
  emulate -L zsh
  _wsh_runtime_disable_reader
  if [[ -n $WSH_RUNTIME_INPUT_FD ]]; then
    (( WSH_RUNTIME_REQUEST_ID++ ))
    print -r -u $WSH_RUNTIME_INPUT_FD -- "{\"type\":\"shutdown\",\"version\":1,\"id\":${WSH_RUNTIME_REQUEST_ID}}" 2>/dev/null || true
    local stopped
    local -F stop_deadline=$(( EPOCHREALTIME + 3 )) remaining
    while (( (remaining = stop_deadline - EPOCHREALTIME) > 0 )); do
      read -r -t $remaining -u $WSH_RUNTIME_OUTPUT_FD stopped 2>/dev/null || break
      [[ $stopped == '{"version":1,"type":"stopping","id":'* ]] && break
    done
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

_wsh_runtime_failed() {
  emulate -L zsh
  _wsh_runtime_disable_reader
  WSH_RUNTIME_READY=0
  PROMPT=$WSH_LAST_PROMPT
  RPROMPT=$WSH_LAST_RPROMPT
  if [[ -n $WSH_RUNTIME_INPUT_FD ]]; then
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
}

_wsh_runtime_apply_snapshot() {
  emulate -L zsh
  setopt extendedglob
  local line=$1 generation prompt_hex rprompt_hex next_prompt next_rprompt
  [[ $line == '{"version":1,"type":"snapshot","id":'* ]] || return 0
  generation=${${line#*\"generation\":}%%,*}
  [[ $generation == <-> && $generation -eq $WSH_RUNTIME_GENERATION ]] || return 0
  prompt_hex=${${line#*\"prompt_hex\":\"}%%\"*}
  rprompt_hex=${${line#*\"rprompt_hex\":\"}%%\"*}
  [[ $prompt_hex == [[:xdigit:]]# && $rprompt_hex == [[:xdigit:]]# ]] || return 0
  (( ${#prompt_hex} % 2 == 0 && ${#rprompt_hex} % 2 == 0 )) || return 0
  _wsh_hex_decode "$prompt_hex"
  next_prompt=$REPLY
  _wsh_hex_decode "$rprompt_hex"
  next_rprompt=$REPLY
  [[ $next_prompt == $WSH_LAST_PROMPT && $next_rprompt == $WSH_LAST_RPROMPT ]] && return 0
  WSH_LAST_PROMPT=$next_prompt
  WSH_LAST_RPROMPT=$next_rprompt
  PROMPT=$WSH_LAST_PROMPT
  RPROMPT=$WSH_LAST_RPROMPT
  (( WSH_RUNTIME_REPAINTS++ ))
  zle reset-prompt 2>/dev/null || true
}

_wsh_runtime_read() {
  emulate -L zsh
  local line
  if ! read -r -u $WSH_RUNTIME_OUTPUT_FD line 2>/dev/null; then
    _wsh_runtime_failed
    return 0
  fi
  _wsh_runtime_apply_snapshot "$line"
  while read -r -t 0 -u $WSH_RUNTIME_OUTPUT_FD line 2>/dev/null; do
    _wsh_runtime_apply_snapshot "$line"
  done
}

_wsh_runtime_preexec() {
  emulate -L zsh
  WSH_COMMAND_STARTED_AT=$EPOCHREALTIME
  [[ $1 == clear || $1 == 'clear '* ]] && WSH_RESET_TRANSIENT=1
  if (( WSH_RUNTIME_READY )); then
    (( WSH_RUNTIME_REQUEST_ID++ ))
    print -r -u $WSH_RUNTIME_INPUT_FD -- "{\"type\":\"cancel\",\"version\":1,\"id\":${WSH_RUNTIME_REQUEST_ID},\"generation\":${WSH_RUNTIME_GENERATION}}" 2>/dev/null || _wsh_runtime_failed
  fi
}

_wsh_runtime_precmd() {
  local -i exit_status=$?
  emulate -L zsh
  local duration_json=null
  local -F now
  local -i duration_ms
  if (( WSH_COMMAND_STARTED_AT > 0 )); then
    now=$EPOCHREALTIME
    duration_ms=$(( (now - WSH_COMMAND_STARTED_AT) * 1000 ))
    duration_json=$duration_ms
    WSH_COMMAND_STARTED_AT=0
  fi
  PROMPT=$WSH_LAST_PROMPT
  RPROMPT=$WSH_LAST_RPROMPT
  (( WSH_RUNTIME_READY )) || return 0
  _wsh_hex_encode "$PWD"
  (( WSH_RUNTIME_GENERATION++ ))
  (( WSH_RUNTIME_REQUEST_ID++ ))
  local privileged=false
  (( EUID == 0 )) && privileged=true
  local reset_transient=false
  (( WSH_RESET_TRANSIENT )) && reset_transient=true
  WSH_RESET_TRANSIENT=0
  print -r -u $WSH_RUNTIME_INPUT_FD -- "{\"type\":\"refresh\",\"version\":1,\"id\":${WSH_RUNTIME_REQUEST_ID},\"generation\":${WSH_RUNTIME_GENERATION},\"cwd_hex\":\"${REPLY}\",\"exit_status\":${exit_status},\"duration_ms\":${duration_json},\"privileged\":${privileged},\"reset_transient\":${reset_transient}}" 2>/dev/null || _wsh_runtime_failed
}

_wsh_runtime_start() {
  emulate -L zsh
  if [[ ! -x ${WSH_RUNTIME:-} || ! -f ${WSH_THEME:-} ]]; then
    print -u2 -- 'wsh: WSH_RUNTIME or WSH_THEME is unavailable'
    return 1
  fi

  unsetopt monitor
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
  zle -F $WSH_RUNTIME_OUTPUT_FD _wsh_runtime_read
}

zmodload zsh/datetime
autoload -Uz add-zsh-hook
add-zsh-hook preexec _wsh_runtime_preexec
add-zsh-hook precmd _wsh_runtime_precmd
add-zsh-hook zshexit _wsh_runtime_stop
_wsh_runtime_start
