#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o extended_glob
zmodload zsh/datetime

local root=${0:A:h:h}
local runtime=${WSH_TRACE_RUNTIME:-$root/target/release/wsh-runtime}
local theme=${WSH_TRACE_THEME:-$root/benchmarks/wsh-benchmark.toml}
local -i iterations=${WSH_TRACE_ITERATIONS:-20}

runtime=${runtime:A}
theme=${theme:A}
[[ $iterations == <1-> ]] || {
  print -u2 -- 'WSH_TRACE_ITERATIONS must be a positive integer'
  return 2
}
[[ -x $runtime && -r $theme ]] || {
  print -u2 -- 'trace benchmark requires runtime and theme inputs'
  return 2
}

local scratch
scratch=$(mktemp -d /var/tmp/wsh-trace-overhead.XXXXXX)
local fixture=$scratch/fixture
local -i runtime_pid=0 runtime_input_fd=-1 runtime_output_fd=-1 request_id=0 generation=0

stop_runtime() {
  if (( runtime_input_fd >= 0 )); then
    (( ++request_id ))
    print -r -u $runtime_input_fd -- "{\"type\":\"shutdown\",\"version\":1,\"id\":${request_id}}" 2>/dev/null || true
    exec {runtime_input_fd}>&- 2>/dev/null || true
    runtime_input_fd=-1
  fi
  if (( runtime_output_fd >= 0 )); then
    exec {runtime_output_fd}<&- 2>/dev/null || true
    runtime_output_fd=-1
  fi
  if (( runtime_pid > 0 )); then
    wait $runtime_pid 2>/dev/null || true
    runtime_pid=0
  fi
}

cleanup() {
  stop_runtime
  command rm -rf -- $scratch
}
trap cleanup EXIT INT TERM

command git init -q -b main $fixture
command git -C $fixture config user.name 'wsh trace benchmark'
command git -C $fixture config user.email trace@wsh.invalid
local -i file_index
for (( file_index = 1; file_index <= 1000; ++file_index )); do
  print -r -- seed > $fixture/file-$file_index
done
command git -C $fixture add .
command git -C $fixture commit -qm initial

local cwd_hex
cwd_hex=$(printf %s $fixture | command od -An -tx1 | command tr -d ' \n')
[[ $cwd_hex == [[:xdigit:]]# ]] || return 1

start_runtime() {
  local mode=$1 ready trace_file=$2
  local -i elapsed_us
  local -F started=$EPOCHREALTIME
  if [[ $mode == traced ]]; then
    command rm -f -- $trace_file
    coproc env WSH_TRACE_FILE=$trace_file $runtime serve --theme $theme
  else
    coproc $runtime serve --theme $theme
  fi
  runtime_pid=$!
  exec {runtime_input_fd}>&p
  exec {runtime_output_fd}<&p
  disown %%
  read -r -t 2 -u $runtime_output_fd ready || return 1
  [[ $ready == '{"version":1,"type":"ready","theme":"benchmark"}' ]] || return 1
  elapsed_us=$(( (EPOCHREALTIME - started) * 1000000 + 0.5 ))
  REPLY=$elapsed_us
}

refresh() {
  local response
  (( ++request_id, ++generation ))
  print -r -u $runtime_input_fd -- "{\"type\":\"refresh\",\"version\":1,\"id\":${request_id},\"generation\":${generation},\"cwd_hex\":\"${cwd_hex}\",\"exit_status\":0,\"duration_ms\":null,\"privileged\":false,\"reset_transient\":false}"
  read -r -t 2 -u $runtime_output_fd response || return 1
  [[ $response == '{"version":1,"type":"snapshot","id":'* ]] || return 1
}

prepare_state() {
  local state=$1
  command git -C $fixture restore .
  command rm -f -- $fixture/untracked
  if [[ $state == clean ]]; then
    print -r -- changed >> $fixture/file-1
  fi
}

apply_state() {
  local state=$1
  case $state in
    clean) print -r -- seed > $fixture/file-1 ;;
    dirty) print -r -- changed >> $fixture/file-1 ;;
    untracked) print -r -- untracked > $fixture/untracked ;;
  esac
}

measure_session() {
  local mode=$1 state=$2 trace_file=$3
  local -i ready_us refresh_us
  prepare_state $state
  start_runtime $mode $trace_file
  ready_us=$REPLY
  refresh
  apply_state $state
  refresh
  prepare_state $state
  refresh
  apply_state $state
  local -F started=$EPOCHREALTIME
  refresh
  refresh_us=$(( (EPOCHREALTIME - started) * 1000000 + 0.5 ))
  stop_runtime
  REPLY="${ready_us}:${refresh_us}"
}

print -r -- $'state\titeration\torder\tplain_ready_us\ttraced_ready_us\tready_overhead_us\tplain_refresh_us\ttraced_refresh_us\trefresh_overhead_us'
local state order plain_result traced_result trace_file
local -i iteration plain_ready traced_ready plain_refresh traced_refresh
for state in clean dirty untracked; do
  for (( iteration = 1; iteration <= iterations; ++iteration )); do
    trace_file=$scratch/trace-${state}-${iteration}.jsonl
    if (( iteration % 2 )); then
      order=plain-first
      measure_session plain $state $trace_file
      plain_result=$REPLY
      measure_session traced $state $trace_file
      traced_result=$REPLY
    else
      order=traced-first
      measure_session traced $state $trace_file
      traced_result=$REPLY
      measure_session plain $state $trace_file
      plain_result=$REPLY
    fi
    plain_ready=${plain_result%%:*}
    plain_refresh=${plain_result##*:}
    traced_ready=${traced_result%%:*}
    traced_refresh=${traced_result##*:}
    printf '%s\t%d\t%s\t%d\t%d\t%d\t%d\t%d\t%d\n' \
      $state $iteration $order $plain_ready $traced_ready $(( traced_ready - plain_ready )) \
      $plain_refresh $traced_refresh $(( traced_refresh - plain_refresh ))
  done
done
