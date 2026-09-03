#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
zmodload zsh/datetime zsh/zpty zsh/zselect

usage() {
  print -r -- 'usage: benchmark-first-editable.zsh OUTPUT MANAGER BUNDLE'
}

(( $# == 3 )) || {
  usage >&2
  exit 2
}

readonly output=${1:A}
readonly manager=${2:A}
readonly bundle=${3:A}
[[ ! -e $output && ! -L $output ]] || {
  print -u2 -- "error: output already exists: $output"
  exit 1
}
[[ -x $manager && -x $bundle/bin/zsh && -x $bundle/bin/wsh-runtime ]] || {
  print -u2 -- 'error: manager and complete bundle must exist'
  exit 2
}

for command in date git mkdir mktemp mv rm sed taskset; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done

readonly repetitions=20
readonly warmups=5
readonly cpu=${WSH_FIRST_EDITABLE_CPU:-0}
local staging scratch state_root fixture raw_zdotdir
staging=$(mktemp "${output:h}/.${output:t}.XXXXXX")
scratch=$(mktemp -d /var/tmp/wsh-first-editable.XXXXXX)
state_root=$scratch/state
fixture=$scratch/fixture
raw_zdotdir=$scratch/raw-zdotdir
local current_pty= runtime_pid=

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $staging $scratch
}
trap cleanup EXIT INT TERM

$manager bundle activate $bundle --state-root $state_root >/dev/null
command mkdir -p -- $fixture $raw_zdotdir
command git init -q -b main $fixture
command git -C $fixture config user.name 'wsh startup benchmark'
command git -C $fixture config user.email startup@wsh.invalid
local index
for index in {1..1000}; do
  print -r -- $index > $fixture/file-$index
done
command git -C $fixture add .
command git -C $fixture commit -qm seed
print -r -- "PROMPT='WSH_RAW_READY> '" > $raw_zdotdir/.zshrc

local current_variant
first_editable_child() {
  builtin cd -q -- $fixture
  export TERM=xterm-256color
  command stty -echo
  case $current_variant in
    raw)
      export ZDOTDIR=$raw_zdotdir
      exec taskset -c $cpu $bundle/bin/zsh -d
      ;;
    direct-complete)
      export WSH_BUNDLE_ROOT=$bundle
      export WSH_RUNTIME=$bundle/bin/wsh-runtime
      export WSH_THEME=$bundle/share/wsh/themes/minimal.toml
      export ZDOTDIR=$bundle/share/wsh/zdotdir
      exec taskset -c $cpu $bundle/bin/zsh -d
      ;;
    managed-complete)
      export WSH_STATE_ROOT=$state_root
      exec taskset -c $cpu $manager
      ;;
    *)
      print -u2 -- "error: unknown variant: $current_variant"
      return 1
      ;;
  esac
}

measure_variant() {
  local variant=$1 block=$2 position=$3 repetition=$4
  local prompt_marker chunk output_buffer=''
  local -F started=$EPOCHREALTIME deadline elapsed_ms
  current_variant=$variant
  current_pty=wsh_first_editable_${$}_${block}_${position}_${repetition}
  if [[ $variant == raw ]]; then
    prompt_marker='WSH_RAW_READY> '
  elif (( EUID == 0 )); then
    prompt_marker='# '
  else
    prompt_marker='% '
  fi

  zpty -b $current_pty first_editable_child
  local pty_fd=$REPLY
  deadline=$(( started + 5 ))
  while (( EPOCHREALTIME < deadline )); do
    while zpty -r -t $current_pty chunk 2>/dev/null; do
      output_buffer+=$chunk
      if [[ $output_buffer == *$prompt_marker* ]]; then
        elapsed_ms=$(( (EPOCHREALTIME - started) * 1000 ))
        printf '%s\t%s\t%d\t%s\t%d\t%.6f\n' \
          "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $block $position $variant $repetition $elapsed_ms >> $staging
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

print -r -- $'measured_at_utc\tblock\tposition\tvariant\trepetition\tfirst_editable_ms' > $staging

local variant repetition block position
for variant in raw direct-complete managed-complete; do
  for repetition in {1..$warmups}; do
    measure_variant $variant warmup 0 $repetition
  done
done
command sed -i '/\twarmup\t/d' $staging

local -a order
for block in forward reverse; do
  if [[ $block == forward ]]; then
    order=(raw direct-complete managed-complete)
  else
    order=(managed-complete direct-complete raw)
  fi
  position=0
  for variant in $order; do
    (( position += 1 ))
    for repetition in {1..$repetitions}; do
      measure_variant $variant $block $position $repetition
    done
  done
done

mv -- $staging $output
trap - EXIT INT TERM
command rm -rf -- $scratch
print -r -- $output
