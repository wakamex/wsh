#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 3 )) || {
  print -u2 -- 'usage: benchmark-native-terminal-integration.zsh ZSH WAKTERM_INTEGRATION OUTPUT'
  exit 2
}

readonly zsh_binary=${1:A}
readonly wakterm_integration=${2:A}
readonly output=${3:A}
readonly warmups=${WSH_BENCH_WARMUPS:-5}
readonly retained=${WSH_BENCH_RETAINED:-40}
readonly commands_per_run=${WSH_BENCH_COMMANDS:-100}
readonly test_root=$(mktemp -d /var/tmp/wsh-native-terminal-benchmark.XXXXXX)
readonly home=$test_root/home
typeset -g current_variant= current_pty= pty_output=

[[ -x $zsh_binary && -r $wakterm_integration && $warmups == <0-> && $retained == <1-> && $commands_per_run == <1-> ]] || {
  print -u2 -- 'error: invalid benchmark argument'
  exit 2
}

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $test_root
}
trap cleanup EXIT INT TERM

command mkdir -p -- $home ${output:h}
print -r -- 'typeset -ga .term.extensions=(-query)' >| $home/.zshenv
print -r -- "PS1='WSH_BENCH> '
PS2='WSH_CONTINUE> '
if [[ \$WSH_BENCH_VARIANT != native ]]; then
  typeset -gx WAKTERM_SHELL_SKIP_USER_VARS=1
  source ${(q)wakterm_integration}
fi" >| $home/.zshrc

benchmark_child() {
  local variant=$1
  export HOME=$home ZDOTDIR=$home TERM=xterm-256color WSH_BENCH_VARIANT=$variant
  unset WAKTERM_SHELL_SKIP_ALL WAKTERM_SHELL_SKIP_SEMANTIC_ZONES WAKTERM_SHELL_SKIP_CWD
  if [[ $variant == coexist ]]; then
    export WSH_NATIVE_TERMINAL_INTEGRATION=1
  else
    unset WSH_NATIVE_TERMINAL_INTEGRATION
  fi
  command stty -echo
  exec $zsh_binary -di
}

read_available() {
  local chunk
  while zpty -r -t $current_pty chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

marker_count() {
  local marker=$'\e]133;B\e\\'
  local without=${pty_output//$marker/}
  reply=$(( (${#pty_output} - ${#without}) / ${#marker} ))
}

wait_for_markers() {
  local target=$1 label=$2
  local -F deadline=$(( EPOCHREALTIME + 30 ))
  while (( EPOCHREALTIME < deadline )); do
    read_available
    marker_count
    (( reply >= target )) && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -- "timeout waiting for ${label}: expected ${target} prompt markers, saw ${reply}"
  return 1
}

run_batch() {
  local count=$1 label=$2
  marker_count
  local target=$(( reply + count ))
  local input=
  repeat $count input+=$':\n'
  zpty -w -n $current_pty $input
  wait_for_markers $target $label
}

run_sample() {
  local variant=$1 iteration=$2 order=$3
  current_variant=$variant
  current_pty=wsh_terminal_bench_${variant}_${iteration}_${RANDOM}_${$}
  pty_output=
  zpty -b $current_pty benchmark_child $variant
  wait_for_markers 1 initial-prompt
  run_batch 10 internal-warmup
  local -F started=$EPOCHREALTIME
  run_batch $commands_per_run measured-commands
  local -F elapsed_ms=$(( (EPOCHREALTIME - started) * 1000.0 ))
  print -r -- "${variant}"$'\t'"${iteration}"$'\t'"${order}"$'\t'"${elapsed_ms}" >> $output
  zpty -w $current_pty exit
  zpty -d $current_pty 2>/dev/null || true
  current_pty=
}

print -r -- $'variant\titeration\torder\telapsed_ms' >| $output
typeset -a forward=(native duplicate coexist)
typeset -a reverse=(coexist duplicate native)
typeset -i round
for (( round = 1; round <= warmups + retained; round++ )); do
  if (( round % 2 )); then
    variants=("${forward[@]}")
    order=forward
  else
    variants=("${reverse[@]}")
    order=reverse
  fi
  for current_variant in "${variants[@]}"; do
    run_sample $current_variant $round $order
  done
done

print -r -- "PASS: recorded ${retained} retained runs after ${warmups} warmups for each variant"
