#!/usr/bin/env zsh
# Temporary macOS diagnosis: start a shell under zpty the way the suite does, type a
# command, and report whether it ran. Usage: zpty-probe.zsh SHELL ARGS...
zmodload zsh/zpty zsh/zselect zsh/datetime
local -a shell_args=("$@")
probe() {
  local name=$1 blocking=$2 echo=$3 out= chunk
  child() {
    export HOME=$TMPDIR/probe-home ZDOTDIR=$TMPDIR/probe-home TERM=xterm-256color PS1='READY> '
    mkdir -p $HOME
    [[ $echo == noecho ]] && command stty -echo
    exec "${shell_args[@]}"
  }
  if [[ $blocking == b ]]; then zpty -b $name child; else zpty $name child; fi
  local -F end=$(( EPOCHREALTIME + 8 ))
  while (( EPOCHREALTIME < end )) && [[ $out != *'READY> '* ]]; do
    zpty -r -t $name chunk 2>/dev/null && out+=$chunk || zselect -t 5
  done
  local prompt=$#out
  zpty -w $name 'print PROBE_$((6*7))'
  end=$(( EPOCHREALTIME + 4 ))
  while (( EPOCHREALTIME < end )) && [[ $out != *PROBE_42* ]]; do
    zpty -r -t $name chunk 2>/dev/null && out+=$chunk || zselect -t 5
  done
  local result=LOST; [[ $out == *PROBE_42* ]] && result=ran
  print -r -- "$result  prompt=$(( prompt > 0 ))  zpty=${blocking:-nb} $echo  ${shell_args[*]}"
  [[ $result == ran ]] || print -r -- "    output: ${(qqq)out[-600,-1]}"
  zpty -d $name 2>/dev/null
}
probe p1 b noecho
probe p2 b echo
probe p3 '' noecho
probe p4 '' echo
