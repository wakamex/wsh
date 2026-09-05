# Wsh profile API 1

if [[ -z ${WSH_PROFILE_FILE:-} || -z ${WSH_PROFILE_ZPROF_FILE:-} || -z ${WSH_PROFILE_STARTED_AT:-} ]]; then
  return 0
fi

zmodload zsh/datetime zsh/system zsh/stat || return 0
if [[ ${WSH_PROFILE_FUNCTIONS:-0} == 1 ]]; then
  zmodload zsh/zprof || return 0
fi
typeset -gi WSH_PROFILE_FD=-1
if [[ ! -f $WSH_PROFILE_FILE || -L $WSH_PROFILE_FILE ]] || ! sysopen -a -o cloexec -u WSH_PROFILE_FD $WSH_PROFILE_FILE; then
  print -u2 -- 'wsh: could not open the profile trace'
  return 0
fi
typeset -ga _WSH_PROFILE_INITIAL_STAT
zstat -A _WSH_PROFILE_INITIAL_STAT +size $WSH_PROFILE_FILE || return 0
typeset -gi WSH_PROFILE_ZSH_BYTES=$_WSH_PROFILE_INITIAL_STAT[1]
typeset -gi WSH_PROFILE_BUFFERING=1
typeset -ga WSH_PROFILE_BUFFER=()
typeset -gi WSH_PROFILE_SNAPSHOT_APPLIED_AT_US=-1
typeset -gi WSH_PROFILE_SNAPSHOT_APPLIED_DURATION_US=-1
typeset -gi WSH_PROFILE_SNAPSHOT_APPLIED_GENERATION=0
unset _WSH_PROFILE_INITIAL_STAT

_wsh_profile_event() {
  emulate -L zsh
  setopt extendedglob
  local event=$1 extra=''
  [[ $event == [a-z-]## ]] || return 1
  local -F now=$EPOCHREALTIME
  local -i elapsed_us=$(( (now - WSH_PROFILE_STARTED_AT) * 1000000 + 0.5 ))
  if (( $# >= 2 )); then
    [[ $2 == <-> ]] || return 1
    extra+=',"duration_us":'$2
  fi
  if (( $# >= 3 )); then
    [[ $3 == <-> ]] || return 1
    extra+=',"generation":'$3
  fi
  _wsh_profile_write '{"schema_version":1,"source":"zsh","event":"'${event}'","elapsed_us":'${elapsed_us}${extra}'}'
}

_wsh_profile_write() {
  emulate -L zsh
  local line=$1
  (( WSH_PROFILE_ZSH_BYTES + ${#line} + 1 <= 1024 * 1024 )) || return 0
  (( WSH_PROFILE_ZSH_BYTES += ${#line} + 1 ))
  if (( WSH_PROFILE_BUFFERING )); then
    WSH_PROFILE_BUFFER+=($line)
  else
    print -r -u $WSH_PROFILE_FD -- $line
  fi
}

_wsh_profile_flush() {
  emulate -L zsh
  (( ${#WSH_PROFILE_BUFFER} )) && print -rl -u $WSH_PROFILE_FD -- "${WSH_PROFILE_BUFFER[@]}"
  WSH_PROFILE_BUFFER=()
}

_wsh_profile_ownership() {
  emulate -L zsh
  setopt extendedglob
  local history=${WSH_HISTORY_SUBSTRING_SEARCH_OWNER:-unavailable}
  local autosuggestions=${WSH_AUTOSUGGESTIONS_OWNER:-unavailable}
  local syntax=${WSH_SYNTAX_HIGHLIGHTING_OWNER:-unavailable}
  [[ $history == [a-z0-9-]## ]] || history=unavailable
  [[ $autosuggestions == [a-z0-9-]## ]] || autosuggestions=unavailable
  [[ $syntax == [a-z0-9-]## ]] || syntax=unavailable
  local -F now=$EPOCHREALTIME
  local -i elapsed_us=$(( (now - WSH_PROFILE_STARTED_AT) * 1000000 + 0.5 ))
  _wsh_profile_write '{"schema_version":1,"source":"zsh","event":"builtin-ownership","elapsed_us":'${elapsed_us}',"history_owner":"'${history}'","autosuggestions_owner":"'${autosuggestions}'","syntax_owner":"'${syntax}'"}'
}

_wsh_profile_editor_ready() {
  emulate -L zsh
  _wsh_profile_ownership
  WSH_PROFILE_BUFFERING=0
  _wsh_profile_flush
  if [[ ${WSH_PROFILE_FUNCTIONS:-0} == 1 ]]; then
    zprof >| $WSH_PROFILE_ZPROF_FILE
    zprof -c
  fi
  _wsh_profile_event editor-ready
  WSH_PROFILE_BUFFERING=1
  add-zle-hook-widget -d zle-line-init _wsh_profile_editor_ready 2>/dev/null || true
}

_wsh_profile_finish() {
  emulate -L zsh
  if (( WSH_PROFILE_SNAPSHOT_APPLIED_AT_US >= 0 )); then
    _wsh_profile_write '{"schema_version":1,"source":"zsh","event":"snapshot-applied","elapsed_us":'${WSH_PROFILE_SNAPSHOT_APPLIED_AT_US}',"duration_us":'${WSH_PROFILE_SNAPSHOT_APPLIED_DURATION_US}',"generation":'${WSH_PROFILE_SNAPSHOT_APPLIED_GENERATION}'}'
  fi
  _wsh_profile_event shell-exit
  WSH_PROFILE_BUFFERING=0
  _wsh_profile_flush
  if (( WSH_PROFILE_FD >= 0 )); then
    exec {WSH_PROFILE_FD}>&-
    WSH_PROFILE_FD=-1
  fi
  if [[ -x ${WSH_PROFILE_REPORTER:-} && -d ${WSH_PROFILE_DIRECTORY:-} ]]; then
    command $WSH_PROFILE_REPORTER profile report $WSH_PROFILE_DIRECTORY
  fi
}

_wsh_profile_install() {
  emulate -L zsh
  autoload -Uz add-zle-hook-widget add-zsh-hook
  add-zle-hook-widget zle-line-init _wsh_profile_editor_ready
  add-zsh-hook zshexit _wsh_profile_finish
  typeset +x WSH_PROFILE_DIRECTORY WSH_PROFILE_FILE WSH_PROFILE_ZPROF_FILE WSH_PROFILE_REPORTER WSH_PROFILE_FUNCTIONS WSH_PROFILE_STARTED_UNIX_US WSH_PROFILE_STARTED_AT WSH_TRACE_FILE
}

_wsh_profile_event zsh-startup-enter
