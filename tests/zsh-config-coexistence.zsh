#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 3 )) || {
  print -u2 -- 'usage: zsh-config-coexistence.zsh MANAGER BUNDLE present|missing'
  exit 2
}

readonly manager=${1:A}
readonly bundle=${2:A}
readonly expectation=$3
[[ -x $manager && -x $bundle/bin/zsh && ( $expectation == present || $expectation == missing ) ]] || {
  print -u2 -- 'error: invalid manager, bundle, or expectation'
  exit 2
}

readonly scratch=$(mktemp -d /var/tmp/wsh-config-coexistence.XXXXXX)
readonly initial_zdotdir=$scratch/initial
readonly redirected_zdotdir=$scratch/redirected
readonly state_root=$scratch/state
typeset -g current_pty=
typeset -g pty_output=

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $scratch
}
trap cleanup EXIT INT TERM

command mkdir -p -- $initial_zdotdir $redirected_zdotdir $state_root
$manager bundle activate $bundle --state-root $state_root >/dev/null

print -r -- 'print -r -- zshenv >> $WSH_STARTUP_LOG
typeset -gx ZDOTDIR=$WSH_REDIRECTED_ZDOTDIR' > $initial_zdotdir/.zshenv
print -r -- 'print -r -- zprofile >> $WSH_STARTUP_LOG' > $redirected_zdotdir/.zprofile
print -r -- 'print -r -- zshrc >> $WSH_STARTUP_LOG
alias wsh_config_probe="print -r -- WSH_USER_CONFIG_LOADED"
fpath=(/wsh-test-duplicate /wsh-test-duplicate $fpath)
module_path=(/wsh-test-module-duplicate /wsh-test-module-duplicate $module_path)
setopt shwordsplit
autoload -Uz add-zsh-hook
_wsh_user_preexec() { print -r -- user-preexec >> $WSH_STARTUP_LOG }
_wsh_user_precmd() { print -r -- user-precmd >> $WSH_STARTUP_LOG }
_wsh_user_zshexit() { print -r -- user-zshexit >> $WSH_STARTUP_LOG }
add-zsh-hook preexec _wsh_user_preexec
add-zsh-hook precmd _wsh_user_precmd
add-zsh-hook zshexit _wsh_user_zshexit
print -r -- WSH_ZSHRC_LOADED' > $redirected_zdotdir/.zshrc
print -r -- 'print -r -- zlogin >> $WSH_STARTUP_LOG' > $redirected_zdotdir/.zlogin
print -r -- 'print -r -- zlogout >> $WSH_STARTUP_LOG' > $redirected_zdotdir/.zlogout

pty_read_available() {
  local chunk
  while zpty -r -t $current_pty chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

pty_wait_for() {
  local expected=$1
  local -F deadline=$(( EPOCHREALTIME + ${2:-3} ))
  while (( EPOCHREALTIME < deadline )); do
    pty_read_available
    [[ $pty_output == *$expected* ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  pty_read_available
  print -u2 -r -- "timeout waiting for ${(qqq)expected}: ${(qqq)pty_output}"
  return 1
}

typeset -g child_login=0 child_log= child_home=$initial_zdotdir child_redirected=$redirected_zdotdir
managed_child() {
  export HOME=$child_home
  export ZDOTDIR=$child_home
  export WSH_STARTUP_LOG=$child_log
  export WSH_REDIRECTED_ZDOTDIR=$child_redirected
  export WSH_STATE_ROOT=$state_root
  export TERM=xterm-256color
  unset WSH_BUNDLE_ROOT WSH_USER_ZDOTDIR WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  command stty -echo
  if (( child_login )); then
    exec $manager run --state-root $state_root -- -l
  else
    exec $manager run --state-root $state_root
  fi
}

run_interactive() {
  local mode=$1
  child_home=$initial_zdotdir
  child_redirected=$redirected_zdotdir
  child_log=$scratch/${mode}.log
  : >| $child_log
  child_login=0
  [[ $mode == login ]] && child_login=1
  current_pty=wsh_config_${mode}_${$}
  pty_output=
  zpty -b $current_pty managed_child
  pty_wait_for '% ' 5

  zpty -w $current_pty wsh_config_probe
  if [[ $expectation == present ]]; then
    pty_wait_for WSH_USER_CONFIG_LOADED 3
  else
    pty_wait_for 'command not found' 3
  fi

  zpty -w $current_pty 'source $WSH_BUNDLE_ROOT/share/wsh/integration.zsh; print -r -- WSH_HOOKS:${(j:,:)precmd_functions}:${(j:,:)preexec_functions}:${(j:,:)zshexit_functions}'
  pty_wait_for WSH_HOOKS: 3
  zpty -w $current_pty "print -r -- \$'WSH_\\x43ONFIG_STATE:'\${ZDOTDIR}:\${WSH_USER_ZDOTDIR-unset}:\${WSH_RUNTIME_READY}:\${options[globalrcs]}:\${options[shwordsplit]}:\${#\${(M)fpath:#/wsh-test-duplicate}}:\${#\${(M)module_path:#/wsh-test-module-duplicate}}:\${WSH_RUNTIME_PID}"
  pty_wait_for WSH_CONFIG_STATE: 3
  zpty -w $current_pty false
  pty_wait_for '% ' 3
  zpty -w $current_pty exit
  if [[ $expectation == present ]]; then
    local -F exit_deadline=$(( EPOCHREALTIME + 3 ))
    local exit_marker=user-zshexit
    [[ $mode == login ]] && exit_marker=zlogout
    while (( EPOCHREALTIME < exit_deadline )) && [[ $(<$child_log) != *$exit_marker* ]]; do
      zselect -t 1 2>/dev/null || true
    done
  fi
  zpty -d $current_pty 2>/dev/null || true
  current_pty=

  if [[ $expectation == missing ]]; then
    [[ ! -s $child_log ]] || {
      print -u2 -r -- "baseline unexpectedly loaded user startup files: $(<$child_log)"
      return 1
    }
    return 0
  fi

  local expected_log
  if [[ $mode == login ]]; then
    expected_log=$'zshenv\nzprofile\nzshrc\nzlogin\nuser-precmd\nuser-preexec\nuser-precmd\nuser-preexec\nuser-precmd\nuser-preexec\nuser-precmd\nuser-preexec\nuser-precmd\nuser-preexec\nzlogout\nuser-zshexit'
  else
    expected_log=$'zshenv\nzshrc\nuser-precmd\nuser-preexec\nuser-precmd\nuser-preexec\nuser-precmd\nuser-preexec\nuser-precmd\nuser-preexec\nuser-precmd\nuser-preexec\nuser-zshexit'
  fi
  [[ $(<$child_log) == $expected_log ]] || {
    print -u2 -r -- "unexpected $mode startup and hook order: ${(qqq)$(<$child_log)}"
    return 1
  }
  [[ $pty_output == *"WSH_CONFIG_STATE:${redirected_zdotdir}:${redirected_zdotdir}:1:off:on:2:2:"<1->* ]] || {
    print -u2 -r -- "user ZDOTDIR was not restored after $mode startup: ${(qqq)pty_output}"
    return 1
  }
  local hook_line=${${pty_output##*WSH_HOOKS:}%%$'\r\n'*}
  local -a recorded_precmd=(${(s:,:)${hook_line%%:*}})
  local remainder=${hook_line#*:}
  local -a recorded_preexec=(${(s:,:)${remainder%%:*}})
  local -a recorded_zshexit=(${(s:,:)${hook_line##*:}})
  [[ ${(j:,:)recorded_precmd} == _wsh_user_precmd,_wsh_runtime_precmd ]] || return 1
  [[ ${(j:,:)recorded_preexec} == _wsh_user_preexec,_wsh_runtime_preexec ]] || return 1
  [[ ${(j:,:)recorded_zshexit} == _wsh_user_zshexit,_wsh_runtime_stop ]] || return 1
}

readonly noninteractive_log=$scratch/noninteractive.log
: >| $noninteractive_log
noninteractive_output=$(HOME=$initial_zdotdir \
  ZDOTDIR=$initial_zdotdir \
  WSH_STARTUP_LOG=$noninteractive_log \
  WSH_REDIRECTED_ZDOTDIR=$redirected_zdotdir \
  WSH_STATE_ROOT=$state_root \
  $manager run --state-root $state_root -- -c 'print -r -- WSH_NONINTERACTIVE:${ZDOTDIR}:${WSH_INTEGRATION_LOADED-unset}')

if [[ $expectation == present ]]; then
  [[ $(<$noninteractive_log) == zshenv ]] || {
    print -u2 -r -- "non-interactive startup did not load only .zshenv: ${(qqq)$(<$noninteractive_log)}"
    exit 1
  }
  [[ $noninteractive_output == "WSH_NONINTERACTIVE:${redirected_zdotdir}:unset" ]] || {
    print -u2 -r -- "unexpected non-interactive state: ${(qqq)noninteractive_output}"
    exit 1
  }
else
  [[ ! -s $noninteractive_log && $noninteractive_output == *':unset' ]] || {
    print -u2 -r -- "baseline unexpectedly loaded non-interactive user config: ${(qqq)noninteractive_output}"
    exit 1
  }
fi

run_interactive nonlogin
run_interactive login

if [[ $expectation == present ]]; then
  readonly rcs_initial=$scratch/rcs-initial
  readonly rcs_redirected=$scratch/rcs-redirected
  readonly rcs_log=$scratch/rcs.log
  command mkdir -p -- $rcs_initial $rcs_redirected
  print -r -- 'print -r -- rcs-zshenv >> $WSH_STARTUP_LOG
typeset -gx ZDOTDIR=$WSH_REDIRECTED_ZDOTDIR
unsetopt rcs' > $rcs_initial/.zshenv
  print -r -- 'print -r -- unexpected-zshrc >> $WSH_STARTUP_LOG' > $rcs_redirected/.zshrc
  : >| $rcs_log
  child_home=$rcs_initial
  child_redirected=$rcs_redirected
  child_log=$rcs_log
  child_login=0
  current_pty=wsh_config_rcs_${$}
  pty_output=
  zpty -b $current_pty managed_child
  pty_wait_for '% ' 5
  zpty -w $current_pty "print -r -- \$'WSH_\\x52CS_STATE:'\$options[rcs]:\${WSH_INTEGRATION_LOADED-unset}:\${ZDOTDIR}"
  pty_wait_for WSH_RCS_STATE: 3
  [[ $pty_output == *"WSH_RCS_STATE:off:1:${rcs_redirected}"* && $(<$rcs_log) == rcs-zshenv ]] || {
    print -u2 -r -- "RCS or startup-file suppression was not preserved: output=${(qqq)pty_output} log=${(qqq)$(<$rcs_log)}"
    exit 1
  }
  zpty -w $current_pty exit
  zpty -d $current_pty 2>/dev/null || true
  current_pty=
fi
print -r -- "PASS: user startup configuration $expectation under managed wsh"
