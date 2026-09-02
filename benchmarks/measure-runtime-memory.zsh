#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

local root=${0:A:h:h}
local runtime= theme= output=
local -i iterations=100 fixture_files=1000

usage() {
  print -r -- 'usage: measure-runtime-memory.zsh --runtime FILE --theme FILE [--iterations NUM] [--fixture-files NUM] [--output FILE]'
}

fail() {
  print -u2 -r -- "error: $*"
  return 1
}

while (( $# )); do
  case $1 in
    --runtime) runtime=$2; shift 2 ;;
    --theme) theme=$2; shift 2 ;;
    --iterations) iterations=$2; shift 2 ;;
    --fixture-files) fixture_files=$2; shift 2 ;;
    --output) output=$2; shift 2 ;;
    -h|--help) usage; return 0 ;;
    *) fail "unknown option: $1" ;;
  esac
done

[[ -n $runtime && -n $theme ]] || fail 'runtime and theme are required'
runtime=${runtime:A}
theme=${theme:A}
[[ -z $output ]] || output=${output:A}
[[ -x $runtime && -r $theme ]] || fail 'runtime or theme is unavailable'
[[ $iterations == <1-> && $fixture_files == <1-> ]] || fail 'iterations and fixture-files must be positive integers'
if [[ -n $output ]]; then
  [[ -d $output:h && -w $output:h && ! -d $output ]] || fail 'output path is not writable'
fi

local scratch
scratch=$(mktemp -d /var/tmp/wsh-memory.XXXXXX)
local runtime_pid=-1 output_tmp=
cleanup() {
  if (( runtime_pid > 0 )) && kill -0 $runtime_pid 2>/dev/null; then
    kill -KILL $runtime_pid 2>/dev/null || true
  fi
  [[ -z $output_tmp ]] || command rm -f -- $output_tmp
  command rm -rf -- $scratch
}
trap cleanup EXIT INT TERM

local fixture=$scratch/fixture
command git init -q -b main $fixture
command git -C $fixture config user.name 'wsh memory benchmark'
command git -C $fixture config user.email memory@wsh.invalid
local -i index
for (( index = 1; index <= fixture_files; ++index )); do
  print -r -- seed > $fixture/file-$index
done
command git -C $fixture add .
command git -C $fixture commit -qm seed

local cwd_hex
cwd_hex=$(print -rn -- $fixture | command od -An -tx1 | command tr -d ' \n')
local runtime_sha256=$(command sha256sum $runtime | command awk '{ print $1 }')
local theme_sha256=$(command sha256sum $theme | command awk '{ print $1 }')
local runner_sha256=$(command sha256sum ${0:A} | command awk '{ print $1 }')
local wsh_commit=$(command git -C $root rev-parse HEAD)
local git_version=$(command git --version | command awk '{ print $3 }')
local kernel=$(command uname -r)
local observed_at
observed_at=$(command date -u +%Y-%m-%dT%H:%M:%SZ)
local header=$'observed_at_utc\twsh_commit\trunner_sha256\truntime_sha256\ttheme_sha256\tgit_version\tkernel\tfixture_files\tphase\tcompleted_refreshes\tpss_kib\trss_kib'
local -a rows=()

coproc $runtime serve --theme $theme
runtime_pid=$!
local runtime_input runtime_output
exec {runtime_input}>&p
exec {runtime_output}<&p
local response
read -r -t 1 -u $runtime_output response || fail 'runtime did not become ready'
[[ $response == '{"version":1,"type":"ready","theme":'* ]] || fail 'runtime returned an invalid ready message'

sample_memory() {
  local phase=$1 completed=$2 pss rss
  local -a row
  pss=$(command awk '/^Pss:/ { print $2 }' /proc/$runtime_pid/smaps_rollup)
  rss=$(command awk '/^VmRSS:/ { print $2 }' /proc/$runtime_pid/status)
  [[ $pss == <0-> && $rss == <0-> ]] || fail 'could not read runtime memory counters'
  row=($observed_at $wsh_commit $runner_sha256 $runtime_sha256 $theme_sha256 $git_version $kernel $fixture_files $phase $completed $pss $rss)
  rows+=("${(pj:\t:)row}")
}

sample_memory idle 0
for (( index = 1; index <= iterations; ++index )); do
  print -r -u $runtime_input -- "{\"type\":\"refresh\",\"version\":1,\"id\":${index},\"generation\":${index},\"cwd_hex\":\"${cwd_hex}\",\"exit_status\":0,\"duration_ms\":null,\"privileged\":false,\"reset_transient\":false}"
  read -r -t 3 -u $runtime_output response || fail "refresh $index timed out"
  [[ $response == '{"version":1,"type":"snapshot","id":'* ]] || fail "refresh $index returned an invalid response"
  (( index == 1 )) && sample_memory first 1
done
sample_memory retained $iterations

print -r -u $runtime_input -- "{\"type\":\"shutdown\",\"version\":1,\"id\":$(( iterations + 1 ))}"
read -r -t 3 -u $runtime_output response || fail 'shutdown timed out'
exec {runtime_input}>&-
exec {runtime_output}<&-
wait $runtime_pid
runtime_pid=-1

if [[ -n $output ]]; then
  output_tmp=$(command mktemp $output:h/.${output:t}.XXXXXX)
  {
    print -r -- $header
    print -r -l -- $rows
  } > $output_tmp
  command mv -f -- $output_tmp $output
  output_tmp=
fi
print -r -- $header
print -r -l -- $rows
