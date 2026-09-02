#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
zmodload zsh/datetime zsh/zpty zsh/zselect

local root=${0:A:h:h}
local zsh_binary=${WSH_MEMORY_ZSH:-$root/build/out/zsh-5.9.2/bin/zsh}
local runtime=${WSH_MEMORY_RUNTIME:-$root/target/release/wsh-runtime}
local integration=${WSH_MEMORY_INTEGRATION:-$root/integration/integration.zsh}
local theme=${WSH_MEMORY_THEME:-$root/benchmarks/wsh-benchmark.toml}
local bundle_root=${WSH_MEMORY_BUNDLE_ROOT:-${zsh_binary:h:h}}
local -i iterations=${WSH_MEMORY_ITERATIONS:-20}
local -i warmup_prompts=${WSH_MEMORY_WARMUP_PROMPTS:-20}

zsh_binary=${zsh_binary:A}
runtime=${runtime:A}
integration=${integration:A}
theme=${theme:A}
bundle_root=${bundle_root:A}

[[ $iterations == <1-> && $warmup_prompts == <1-> ]] || {
  print -u2 -- 'WSH_MEMORY_ITERATIONS and WSH_MEMORY_WARMUP_PROMPTS must be positive integers'
  return 2
}
[[ -x $zsh_binary && -x $runtime && -r $integration && -r $theme ]] || {
  print -u2 -- 'memory benchmark requires Zsh, runtime, integration, and theme inputs'
  return 2
}
[[ -d $bundle_root/lib/zsh/5.9.2 ]] || {
  print -u2 -- 'memory benchmark requires a complete bundle root'
  return 2
}

local scratch
scratch=$(mktemp -d /var/tmp/wsh-runtime-memory.XXXXXX)
local fixture=$scratch/fixture
local current_pty=
local -i current_runtime_pid=0

cleanup() {
  if [[ -n $current_pty ]]; then
    zpty -d $current_pty 2>/dev/null || true
  fi
  if (( current_runtime_pid > 0 )) && kill -0 $current_runtime_pid 2>/dev/null; then
    kill -KILL $current_runtime_pid 2>/dev/null || true
  fi
  command rm -rf -- $scratch
}
trap cleanup EXIT INT TERM

command git init -q -b main $fixture
command git -C $fixture config user.name 'wsh memory benchmark'
command git -C $fixture config user.email memory@wsh.invalid
local -i file_index
for (( file_index = 1; file_index <= 1000; ++file_index )); do
  print -r -- seed > $fixture/file-$file_index
done
command git -C $fixture add .
command git -C $fixture commit -qm initial

typeset -g pty_output=''

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

memory_child() {
  builtin cd -q -- $fixture
  export TERM=xterm-256color
  export PS1='WSH_MEMORY_BOOT> '
  command stty -echo
  exec $zsh_binary -dfi
}

read_pss_kib() {
  local -i pid=$1
  local name value unit
  while read -r name value unit; do
    if [[ $name == Pss: ]]; then
      [[ $value == <-> && $unit == kB ]] || return 1
      REPLY=$value
      return 0
    fi
  done < /proc/$pid/smaps_rollup
  return 1
}

settle_pty() {
  local -F deadline=$(( EPOCHREALTIME + 0.25 ))
  while (( EPOCHREALTIME < deadline )); do
    zselect -t 1 2>/dev/null || true
    pty_read_available
  done
}

run_session() {
  local mode=$1
  local marker setup pids result children
  local -i shell_pid runtime_pid=0 prompt_index shell_pss runtime_pss=0

  current_pty="wsh_memory_${mode}_${RANDOM}_${RANDOM}"
  pty_output=''
  zpty -b $current_pty memory_child
  pty_wait_for WSH_MEMORY_BOOT 5

  if [[ $mode == raw ]]; then
    marker=WSH_MEMORY_RAW
    setup="PROMPT=\$'WSH_\\x4dEMORY_RAW> '; RPROMPT=; print -r -- \$'WSH_\\x4dEMORY_SETUP'"
  else
    marker=']ZTB_PROMPT'
    setup="typeset -gx WSH_BUNDLE_ROOT=${(q)bundle_root}; module_path=(${(q)bundle_root}/lib/zsh/5.9.2); fpath=(${(q)bundle_root}/share/zsh/5.9.2/functions \$fpath); typeset -gx WSH_RUNTIME=${(q)runtime} WSH_THEME=${(q)theme}; source ${(q)integration}; (( WSH_RUNTIME_READY )) || return 1; print -r -- \$'WSH_\\x4dEMORY_SETUP'"
  fi
  pty_output=''
  zpty -w $current_pty $setup
  pty_wait_for WSH_MEMORY_SETUP 3
  pty_wait_for $marker 3

  pty_output=''
  zpty -w $current_pty "print -r -- \$'WSH_\\x4dEMORY_PIDS='\$\$:\${WSH_RUNTIME_PID:-0}"
  pty_wait_for WSH_MEMORY_PIDS= 3
  pids=${pty_output##*WSH_MEMORY_PIDS=}
  pids=${pids%%[^0-9:]*}
  shell_pid=${pids%%:*}
  runtime_pid=${pids##*:}
  [[ $shell_pid == <1-> && $runtime_pid == <-> ]] || return 1
  current_runtime_pid=$runtime_pid

  for (( prompt_index = 1; prompt_index <= warmup_prompts; ++prompt_index )); do
    pty_output=''
    zpty -w $current_pty ':'
    pty_wait_for $marker 3
  done
  settle_pty

  read_pss_kib $shell_pid
  shell_pss=$REPLY
  if (( runtime_pid > 0 )); then
    IFS= read -r children < /proc/$runtime_pid/task/$runtime_pid/children || true
    [[ -z $children ]] || {
      print -u2 -r -- "runtime still had children after settling: $children"
      return 1
    }
    read_pss_kib $runtime_pid
    runtime_pss=$REPLY
  fi
  result="${shell_pss}:${runtime_pss}:$(( shell_pss + runtime_pss ))"

  zpty -w $current_pty exit 2>/dev/null || true
  zpty -d $current_pty 2>/dev/null || true
  current_pty=
  current_runtime_pid=0
  REPLY=$result
}

print -r -- $'iteration\torder\traw_zsh_pss_kib\twsh_zsh_pss_kib\twsh_runtime_pss_kib\twsh_combined_pss_kib\tadded_pss_kib'
local iteration order raw_result wsh_result
local -i raw_pss wsh_zsh_pss wsh_runtime_pss wsh_combined_pss
for (( iteration = 1; iteration <= iterations; ++iteration )); do
  if (( iteration % 2 )); then
    order=raw-first
    run_session raw
    raw_result=$REPLY
    run_session wsh
    wsh_result=$REPLY
  else
    order=wsh-first
    run_session wsh
    wsh_result=$REPLY
    run_session raw
    raw_result=$REPLY
  fi
  raw_pss=${raw_result%%:*}
  wsh_zsh_pss=${wsh_result%%:*}
  wsh_result=${wsh_result#*:}
  wsh_runtime_pss=${wsh_result%%:*}
  wsh_combined_pss=${wsh_result##*:}
  printf '%d\t%s\t%d\t%d\t%d\t%d\t%d\n' \
    $iteration $order $raw_pss $wsh_zsh_pss $wsh_runtime_pss $wsh_combined_pss \
    $(( wsh_combined_pss - raw_pss ))
done
