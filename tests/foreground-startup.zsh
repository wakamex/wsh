#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 3 )) || {
  print -u2 -- 'usage: foreground-startup.zsh MANAGER BUNDLE baseline|candidate'
  exit 2
}

readonly manager=${1:A}
readonly bundle=${2:A}
readonly expectation=$3
readonly test_root=$(mktemp -d /var/tmp/wsh-foreground-startup.XXXXXX)
readonly probe=$test_root/foreground-probe
readonly fixture=$test_root/fixture
readonly state_root=$test_root/state
typeset -g current_pty= pty_output= current_variant= current_mode= current_report= current_home=
typeset -ga current_extra_args=()

[[ -x $manager && -x $bundle/bin/zsh && ( $expectation == baseline || $expectation == candidate ) ]] || {
  print -u2 -- 'error: manager, bundle, or expectation is invalid'
  exit 2
}

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $test_root
}
trap cleanup EXIT INT TERM

command mkdir -p -- $fixture
command gcc -std=c11 -O2 -Wall -Wextra -Werror ${0:A:h}/fixtures/foreground-probe.c -o $probe
git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh foreground startup test'
git -C $fixture config user.email foreground-startup@wsh.invalid
print -r -- tracked > $fixture/tracked
git -C $fixture add tracked
git -C $fixture commit -qm initial
$manager bundle activate $bundle --state-root $state_root >/dev/null

write_home() {
  local variant=$1
  local home=$test_root/home-$variant
  command mkdir -p -- $home
  print -r -- 'print -r -- zshenv >> $WSH_TEST_STARTUP_LOG' >| $home/.zshenv
  print -r -- 'print -r -- zprofile >> $WSH_TEST_STARTUP_LOG' >| $home/.zprofile
  print -r -- 'print -r -- zlogin >> $WSH_TEST_STARTUP_LOG' >| $home/.zlogin
  print -r -- 'print -r -- zshrc >> $WSH_TEST_STARTUP_LOG
typeset -g WSH_DISABLE_HISTORY_SUBSTRING_SEARCH=1
typeset -g WSH_DISABLE_AUTOSUGGESTIONS=1
typeset -g WSH_DISABLE_SYNTAX_HIGHLIGHTING=1
alias wsh-foreground-alias="print -r -- WSH_FOREGROUND_ALIAS_OK"
autoload -Uz add-zsh-hook
_wsh_test_foreground_prompt() {
  print -r -- WSH_FOREGROUND_PROMPT
}
add-zsh-hook precmd _wsh_test_foreground_prompt
autoload -Uz add-zle-hook-widget
_wsh_test_foreground_line_init() {
  command stty -g < /dev/tty >> $WSH_TEST_TERMIOS_LOG
}
zle -N _wsh_test_foreground_line_init
add-zle-hook-widget zle-line-init _wsh_test_foreground_line_init
command stty -g < /dev/tty >> $WSH_TEST_TERMIOS_LOG' >| $home/.zshrc
  print -r -- $home
}

foreground_child() {
  builtin cd -q -- $fixture
  export HOME=$current_home
  export ZDOTDIR=$current_home
  export WSH_USER_ZDOTDIR=$current_home
  export WSH_BUNDLE_ROOT=$bundle
  export WSH_RUNTIME=$bundle/bin/wsh-runtime
  export WSH_THEME=$bundle/share/wsh/themes/minimal.toml
  export WSH_TEST_STARTUP_LOG=$current_home/startup.log
  export WSH_TEST_TERMIOS_LOG=$current_home/termios.log
  export TERM=xterm-256color
  unset WSH_RUN_FOREGROUND WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  command stty -echo
  case $current_variant in
    current)
      local invocation="${probe} ${current_report} ${current_mode}"
      exec $bundle/bin/zsh -d -l -i -c "${invocation}; exec \"\$0\" -d -l -i" $bundle/bin/zsh
      ;;
    positional)
      exec $bundle/bin/zsh -d -l -i -c '"$@"; exec "$0" -d -l -i' $bundle/bin/zsh $probe $current_report $current_mode "${current_extra_args[@]}"
      ;;
    candidate)
      exec $manager run-foreground --state-root $state_root --login -- $probe $current_report $current_mode "${current_extra_args[@]}"
      ;;
    candidate-non-login)
      exec $manager run-foreground --state-root $state_root -- $probe $current_report $current_mode "${current_extra_args[@]}"
      ;;
    *)
      print -u2 -- "error: unknown foreground variant: $current_variant"
      return 2
      ;;
  esac
}

read_available() {
  local chunk
  while zpty -r -t $current_pty chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

wait_for_text() {
  local expected=$1 label=$2
  local -F deadline=$(( EPOCHREALTIME + 5 ))
  while (( EPOCHREALTIME < deadline )); do
    read_available
    [[ $pty_output == *$expected* ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -r -- "timeout waiting for ${label}: ${(qqq)pty_output}"
  return 1
}

wait_for_prompt() {
  local label=$1
  wait_for_text $'\e]133;B' $label
}

wait_for_report() {
  local expected=$1
  local -F deadline=$(( EPOCHREALTIME + 3 ))
  while (( EPOCHREALTIME < deadline )); do
    [[ -f $current_report ]] && grep -F -- $expected $current_report >/dev/null && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -- "timeout waiting for report value: $expected"
  return 1
}

wait_for_process_exit() {
  local pid=$1
  local -F deadline=$(( EPOCHREALTIME + 3 ))
  while (( EPOCHREALTIME < deadline )); do
    [[ ! -e /proc/$pid ]] && return 0
    local state=$(sed -n 's/^[^)]*) \([^ ]\).*/\1/p' /proc/$pid/stat 2>/dev/null)
    [[ $state == Z ]] && {
      print -u2 -- "error: foreground process remained a zombie: $pid"
      return 1
    }
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -- "error: foreground process did not exit: $pid"
  return 1
}

process_group() {
  local pid=$1
  sed -n 's/^[^)]*) [^ ]* [^ ]* \([^ ]*\).*/\1/p' /proc/$pid/stat
}

start_variant() {
  current_variant=$1
  current_mode=$2
  shift 2
  current_extra_args=("$@")
  current_home=$(write_home ${current_variant}-${current_mode}-${RANDOM})
  current_report=$current_home/report.tsv
  : >| $current_home/startup.log
  : >| $current_home/termios.log
  current_pty=wsh_foreground_${current_variant//[^A-Za-z0-9]/_}_${RANDOM}_${$}
  pty_output=
  zpty -b $current_pty foreground_child
  wait_for_text $'WSH_FOREGROUND_READY\t' foreground-ready
  local process_line=$(grep '^process' $current_report)
  typeset -ga reply=("${(@ps:\t:)process_line}")
  [[ ${reply[2]} == ${reply[3]} && ${reply[3]} == ${reply[4]} ]] || {
    print -u2 -r -- "foreground process does not own its terminal: ${(qqq)process_line}"
    return 1
  }
}

stop_shell() {
  zpty -w $current_pty exit
  zpty -d $current_pty 2>/dev/null || true
  current_pty=
}

assert_wrapper_loses_suspended_job() {
  local variant=$1
  start_variant $variant wait
  pty_output=
  zpty -w -n $current_pty $'\x1a'
  wait_for_prompt post-suspend-prompt
  pty_output=
  zpty -w $current_pty fg
  wait_for_text 'fg: no current job' lost-job-result
  stop_shell
}

assert_exact_arguments() {
  local -a expected=( '' 'two words' $'line one\nline two' 'quote'\''"' '$HOME' '*' '--leading' 'snowman-☃' $'non-utf8-\xff' )
  start_variant candidate exit0 "${expected[@]}"
  wait_for_prompt post-exit-prompt
  local index actual expected_hex
  for (( index = 1; index <= $#expected; index++ )); do
    actual=$(sed -n "s/^arg\t$(( index + 2 ))\t//p" $current_report)
    expected_hex=$(print -rn -- ${expected[$index]} | od -An -tx1 | tr -d ' \n')
    [[ $actual == $expected_hex ]] || {
      print -u2 -r -- "argument $index changed: expected=${(qqq)expected_hex} actual=${(qqq)actual}"
      return 1
    }
  done
  stop_shell
}

assert_normal_launch_ignores_foreground_environment() {
  local home=$test_root/home-normal-launch
  command mkdir -p -- $home
  print -r -- 'typeset -g WSH_DISABLE_HISTORY_SUBSTRING_SEARCH=1
typeset -g WSH_DISABLE_AUTOSUGGESTIONS=1
typeset -g WSH_DISABLE_SYNTAX_HIGHLIGHTING=1' >| $home/.zshrc
  local output=$(HOME=$home ZDOTDIR=$home WSH_RUN_FOREGROUND=prepared \
    $manager run --state-root $state_root -- -ic 'print -r -- WSH_NORMAL_RUN_OK' 2>&1)
  [[ $output == *WSH_NORMAL_RUN_OK* && $output != *'foreground command is unavailable'* ]]
}

assert_interrupt() {
  start_variant candidate wait
  local pid=${reply[2]}
  pty_output=
  zpty -w -n $current_pty $'\x03'
  wait_for_prompt post-interrupt-prompt
  wait_for_process_exit $pid
  [[ $(grep -c '^zshrc$' $current_home/startup.log) == 1 ]]
  pty_output=
  zpty -w $current_pty :
  wait_for_text WSH_FOREGROUND_PROMPT preserved-user-precmd-hook
  stop_shell
}

assert_consumed_interrupt() {
  start_variant candidate consume-int
  pty_output=
  zpty -w -n $current_pty $'\x03'
  wait_for_report $'signal\tint'
  read_available
  [[ $pty_output != *$'\e]133;B'* ]] || {
    print -u2 -- 'error: shell prompted while foreground process remained alive'
    return 1
  }
  zpty -w $current_pty q
  wait_for_prompt post-consumed-interrupt-prompt
  stop_shell
}

assert_suspend_continue() {
  start_variant candidate wait
  local pid=${reply[2]} pgrp=${reply[3]}
  pty_output=
  zpty -w -n $current_pty $'\x1a'
  wait_for_prompt post-suspend-prompt
  local state=$(sed -n 's/^[^)]*) \([^ ]\).*/\1/p' /proc/$pid/stat)
  [[ $state == T ]]
  pty_output=
  zpty -w $current_pty fg
  wait_for_report $'signal\tcont'
  [[ -e /proc/$pid && $(process_group $pid) == $pgrp ]]
  zpty -w -n $current_pty $'\x03'
  wait_for_prompt post-resume-interrupt-prompt
  wait_for_process_exit $pid
  stop_shell
}

assert_nested_signal_domain() {
  start_variant candidate nested
  local parent_pid=${reply[2]} pgrp=${reply[3]}
  local child_line=$(grep '^child' $current_report)
  local -a child_fields=("${(@ps:\t:)child_line}")
  [[ ${child_fields[3]} == $pgrp ]]
  pty_output=
  zpty -w -n $current_pty $'\x03'
  wait_for_prompt nested-post-interrupt-prompt
  wait_for_process_exit $parent_pid
  wait_for_process_exit ${child_fields[2]}
  stop_shell
}

assert_exit_and_terminal_state() {
  local mode
  for mode in exit0 exit7 termios; do
    start_variant candidate $mode
    wait_for_prompt ${mode}-prompt
    pty_output=
    zpty -w $current_pty :
    wait_for_prompt ${mode}-second-prompt
    local -a settings=(${(f)"$(<$current_home/termios.log)"})
    (( $#settings >= 3 ))
    [[ $settings[-2] == $settings[-1] ]] || {
      print -u2 -- "error: terminal state changed after $mode"
      return 1
    }
    stop_shell
  done
}

assert_startup_modes() {
  start_variant candidate exit0
  wait_for_prompt login-prompt
  for file in zshenv zprofile zshrc zlogin; do
    [[ $(grep -c "^${file}$" $current_home/startup.log) == 1 ]]
  done
  zpty -w $current_pty wsh-foreground-alias
  wait_for_text WSH_FOREGROUND_ALIAS_OK retained-alias
  stop_shell

  start_variant candidate-non-login exit0
  wait_for_prompt non-login-prompt
  [[ $(grep -c '^zshenv$' $current_home/startup.log) == 1 ]]
  [[ $(grep -c '^zshrc$' $current_home/startup.log) == 1 ]]
  ! grep -Eq '^(zprofile|zlogin)$' $current_home/startup.log
  stop_shell
}

assert_repeated_launches() {
  local repetition
  for repetition in {1..20}; do
    start_variant candidate exit0
    wait_for_prompt repeated-prompt
    [[ $(grep -c '^zshrc$' $current_home/startup.log) == 1 ]]
    stop_shell
  done
}

assert_wrapper_loses_suspended_job current
assert_wrapper_loses_suspended_job positional

if [[ $expectation == baseline ]]; then
  print -r -- 'PASS: current and positional wrappers lose the suspended job as expected'
  exit 0
fi

assert_exact_arguments
assert_normal_launch_ignores_foreground_environment
assert_interrupt
assert_consumed_interrupt
assert_suspend_continue
assert_nested_signal_domain
assert_exit_and_terminal_state
assert_startup_modes
assert_repeated_launches

print -r -- 'PASS: structured foreground startup preserves argv, job control, signals, terminal state, startup files, and repeated launch behavior'
