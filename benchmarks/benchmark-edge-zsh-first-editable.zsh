#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 4 )) || {
  print -u2 -- 'usage: benchmark-edge-zsh-first-editable.zsh OUTPUT MANAGER STABLE_BUNDLE EDGE_BUNDLE'
  exit 2
}

readonly output=${1:A}
readonly manager=${2:A}
readonly stable_bundle=${3:A}
readonly edge_bundle=${4:A}
[[ ! -e $output && ! -L $output ]] || {
  print -u2 -- "error: output already exists: $output"
  exit 1
}
[[ -x $manager ]] || {
  print -u2 -- 'error: manager must be executable'
  exit 2
}
for bundle in $stable_bundle $edge_bundle; do
  [[ -x $bundle/bin/zsh && -x $bundle/bin/wsh-runtime ]] || {
    print -u2 -- "error: incomplete bundle: $bundle"
    exit 2
  }
done

for command in date git mkdir mktemp mv rm sed taskset; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done

readonly repetitions=20
readonly warmups=5
readonly cpu=${WSH_FIRST_EDITABLE_CPU:-0}
local staging scratch fixture raw_zdotdir user_zdotdir user_home
staging=$(mktemp "${output:h}/.${output:t}.XXXXXX")
scratch=$(mktemp -d /var/tmp/wsh-edge-first-editable.XXXXXX)
fixture=$scratch/fixture
raw_zdotdir=$scratch/raw-zdotdir
user_zdotdir=$scratch/user-zdotdir
user_home=$scratch/home
local current_pty=

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $staging $scratch
}
trap cleanup EXIT INT TERM

command mkdir -p -- $fixture $raw_zdotdir $user_zdotdir $user_home
command git init -q -b main $fixture
command git -C $fixture config user.name 'wsh edge startup benchmark'
command git -C $fixture config user.email edge-startup@wsh.invalid
local index
for index in {1..1000}; do
  print -r -- $index > $fixture/file-$index
done
command git -C $fixture add .
command git -C $fixture commit -qm seed
print -r -- "PROMPT='WSH_RAW_READY> '" > $raw_zdotdir/.zshrc

local label mode current_bundle current_state_root
first_editable_child() {
  builtin cd -q -- $fixture
  export TERM=xterm-256color
  command stty -echo
  case $mode in
    raw)
      export ZDOTDIR=$raw_zdotdir
      exec taskset -c $cpu $current_bundle/bin/zsh -d
      ;;
    direct)
      export WSH_BUNDLE_ROOT=$current_bundle
      export WSH_RUNTIME=$current_bundle/bin/wsh-runtime
      export WSH_THEME=$current_bundle/share/wsh/themes/minimal.toml
      export WSH_USER_ZDOTDIR=$user_zdotdir
      export ZDOTDIR=$current_bundle/share/wsh/zdotdir
      exec taskset -c $cpu $current_bundle/bin/zsh -d
      ;;
    managed)
      export HOME=$user_home
      export ZDOTDIR=$user_zdotdir
      export WSH_STATE_ROOT=$current_state_root
      exec taskset -c $cpu $manager
      ;;
    *)
      print -u2 -- "error: unknown mode: $mode"
      return 1
      ;;
  esac
}

measure_variant() {
  local variant=$1 block=$2 position=$3 repetition=$4
  local source=${variant##*-}
  mode=${variant%-*}
  label=$variant
  if [[ $source == stable ]]; then
    current_bundle=$stable_bundle
  else
    current_bundle=$edge_bundle
  fi
  current_state_root=$scratch/state-$source

  local prompt_marker chunk output_buffer=''
  local -F started=$EPOCHREALTIME deadline elapsed_ms
  current_pty=wsh_edge_first_editable_${$}_${block}_${position}_${repetition}
  if [[ $mode == raw ]]; then
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

$manager bundle activate $stable_bundle --state-root $scratch/state-stable >/dev/null
$manager bundle activate $edge_bundle --state-root $scratch/state-edge >/dev/null
print -r -- $'measured_at_utc\tblock\tposition\tvariant\trepetition\tfirst_editable_ms' > $staging

local variant repetition block position
local -a variants=(raw-stable raw-edge direct-stable direct-edge managed-stable managed-edge)
for variant in $variants; do
  for repetition in {1..$warmups}; do
    measure_variant $variant warmup 0 $repetition
  done
done
command sed -i '/\twarmup\t/d' $staging

local -a order
for block in forward reverse; do
  if [[ $block == forward ]]; then
    order=($variants)
  else
    order=(managed-edge managed-stable direct-edge direct-stable raw-edge raw-stable)
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
