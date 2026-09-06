#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
zmodload zsh/datetime zsh/zpty zsh/zselect
export WSH_THEME=minimal

(( $# == 4 )) || {
  print -u2 -- 'usage: benchmark-directory-jump.zsh OUTPUT MANAGER BUNDLE ITERATIONS'
  exit 2
}

readonly output=${1:A}
readonly manager=${2:A}
readonly bundle=${3:A}
readonly -i repetitions=$4
readonly -i warmups=5
readonly cpu=${WSH_PROFILE_CPU:-0}
[[ $repetitions -gt 0 && ! -e $output && ! -L $output ]]

for command in cp date git mkdir mktemp mv rm sed taskset; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done

local staging scratch state_root fixture home current_pty= current_variant
staging=$(mktemp "${output:h}/.${output:t}.XXXXXX")
scratch=$(mktemp -d /var/tmp/wsh-directory-jump-benchmark.XXXXXX)
state_root=$scratch/state
fixture=$scratch/fixture
home=$scratch/home

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $staging $scratch
}
trap cleanup EXIT INT TERM

$manager bundle activate $bundle --state-root $state_root >/dev/null
command mkdir -p -- $fixture $home
if [[ -n ${WSH_DIRECTORY_BENCH_ZSHRC:-} ]]; then
  [[ -f $WSH_DIRECTORY_BENCH_ZSHRC && -r $WSH_DIRECTORY_BENCH_ZSHRC ]] || return 2
  command cp -- $WSH_DIRECTORY_BENCH_ZSHRC $home/.zshrc
fi
command git init -q -b main $fixture
command git -C $fixture config user.name 'wsh profile benchmark'
command git -C $fixture config user.email profile-benchmark@wsh.invalid
local index
for index in {1..1000}; do
  print -r -- $index > $fixture/file-$index
done
command git -C $fixture add .
command git -C $fixture commit -qm seed

directory_child() {
  builtin cd -q -- $fixture
  export HOME=$home ZDOTDIR=$home TERM=xterm-256color WSH_STATE_ROOT=$state_root
  command stty -echo
  case $current_variant in
    disabled) export WSH_DISABLE_DIRECTORY_JUMP=1 ;;
    enabled) export WSH_DISABLE_DIRECTORY_JUMP=0 ;;
    *) return 2 ;;
  esac
  exec taskset -c $cpu $manager
}

measure_variant() {
  local variant=$1 block=$2 position=$3 repetition=$4
  local chunk output_buffer='' first_ms= settled_ms=
  local -F started=$EPOCHREALTIME deadline
  current_variant=$variant
  current_pty=wsh_profile_benchmark_${$}_${block}_${position}_${repetition}
  zpty -b $current_pty directory_child
  local pty_fd=$REPLY
  deadline=$(( started + 5 ))
  while (( EPOCHREALTIME < deadline )); do
    while zpty -r -t $current_pty chunk 2>/dev/null; do
      output_buffer+=$chunk
      if [[ -z $first_ms && $output_buffer == *$'\e]133;B\e\\'* ]]; then
        first_ms=$(( (EPOCHREALTIME - started) * 1000 ))
      fi
      if [[ -n $first_ms && $output_buffer == *'git:main'* ]]; then
        settled_ms=$(( (EPOCHREALTIME - started) * 1000 ))
        printf '%s\t%s\t%d\t%s\t%d\t%.6f\t%.6f\n' \
          "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $block $position $variant $repetition $first_ms $settled_ms >> $staging
        zpty -w $current_pty exit
        zselect -r $pty_fd -t 100 2>/dev/null || true
        zpty -d $current_pty 2>/dev/null || true
        current_pty=
        return 0
      fi
    done
    zselect -r $pty_fd -t 1 2>/dev/null || true
  done
  print -u2 -r -- "timeout waiting for $variant prompt: ${(qqq)output_buffer}"
  return 1
}

print -r -- $'measured_at_utc\tblock\tposition\tvariant\trepetition\tfirst_editable_ms\tsettled_ms' > $staging
local variant repetition block position
for variant in disabled enabled; do
  for repetition in {1..$warmups}; do
    measure_variant $variant warmup 0 $repetition
  done
done
command sed -i '/\twarmup\t/d' $staging

local -a order
for block in forward reverse; do
  if [[ $block == forward ]]; then
    order=(disabled enabled)
  else
    order=(enabled disabled)
  fi
  for repetition in {1..$repetitions}; do
    position=0
    for variant in $order; do
      (( position += 1 ))
      measure_variant $variant $block $position $repetition
    done
  done
done

mv -- $staging $output
trap - EXIT INT TERM
command rm -rf -- $scratch
print -r -- $output
