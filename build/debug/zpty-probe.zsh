#!/usr/bin/env zsh
# Temporary macOS diagnosis: start a shell under zpty the way the suite does, type a
# command, and report whether it ran. Usage: zpty-probe.zsh b|nb echo|noecho SHELL ARGS...
zmodload zsh/zpty zsh/zselect zsh/datetime
local mode=$1 echo_mode=$2; shift 2
local -a shell_args=("$@")
step() { print -u2 -r -- "  [$(( EPOCHREALTIME ))] $*"; }
probe() {
  local name=$1 blocking=$2 echo=$3 out= chunk
  child() {
    export HOME=$TMPDIR/probe-home ZDOTDIR=$TMPDIR/probe-home TERM=xterm-256color PS1='READY> '
    mkdir -p $HOME
    [[ $echo == noecho ]] && command stty -echo
    exec "${shell_args[@]}"
  }
  step start
  if [[ $blocking == b ]]; then zpty -b $name child; else zpty $name child; fi
  step started
  local -F end=$(( EPOCHREALTIME + 8 ))
  while (( EPOCHREALTIME < end )) && [[ $out != *'READY> '* ]]; do
    zpty -r -t $name chunk 2>/dev/null && out+=$chunk || zselect -t 5
  done
  local prompt=$#out
  step "prompt bytes $prompt"
  zpty -w $name 'print PROBE_$((6*7))'
  step written
  end=$(( EPOCHREALTIME + 4 ))
  while (( EPOCHREALTIME < end )) && [[ $out != *PROBE_42* ]]; do
    zpty -r -t $name chunk 2>/dev/null && out+=$chunk || zselect -t 5
  done
  local result=LOST; [[ $out == *PROBE_42* ]] && result=ran
  print -r -- "$result  prompt=$(( prompt > 0 ))  zpty=${blocking:-nb} $echo  ${shell_args[*]}"
  [[ $result == ran ]] || print -r -- "    output: ${(qqq)out[-600,-1]}"
  zpty -d $name 2>/dev/null
}
probe p1 "${mode:#nb}" $echo_mode
