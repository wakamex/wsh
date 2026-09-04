#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent
zmodload zsh/datetime zsh/zpty

(( $# == 5 )) || {
  print -u2 -- 'usage: benchmark-managed-builds.zsh OUTPUT BASELINE-MANAGER BASELINE-BUNDLE CANDIDATE-MANAGER CANDIDATE-BUNDLE'
  exit 2
}

readonly output=${1:A}
readonly baseline_manager=${2:A}
readonly baseline_bundle=${3:A}
readonly candidate_manager=${4:A}
readonly candidate_bundle=${5:A}
readonly repetitions=20
readonly warmups=5
readonly cpu=${WSH_FIRST_EDITABLE_CPU:-0}
readonly scratch=$(mktemp -d /var/tmp/wsh-managed-builds.XXXXXX)
readonly staging=$(mktemp "${output:h}/.${output:t}.XXXXXX")
readonly fixture=$scratch/fixture
readonly home=$scratch/home
readonly baseline_state=$scratch/baseline-state
readonly candidate_state=$scratch/candidate-state
typeset -g current_pty= current_build=

[[ ! -e $output && ! -L $output ]] || {
  print -u2 -- "error: output already exists: $output"
  exit 1
}
[[ -x $baseline_manager && -x $baseline_bundle/bin/zsh && -x $candidate_manager && -x $candidate_bundle/bin/zsh ]] || {
  print -u2 -- 'error: both managers and bundles must exist'
  exit 2
}

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $staging $scratch
}
trap cleanup EXIT INT TERM

command mkdir -p -- $fixture $home
: >| $home/.zshrc
git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh managed-build benchmark'
git -C $fixture config user.email managed-build@wsh.invalid
local index
for index in {1..1000}; do
  print -r -- $index > $fixture/file-$index
done
git -C $fixture add .
git -C $fixture commit -qm seed
$baseline_manager bundle activate $baseline_bundle --state-root $baseline_state >/dev/null
$candidate_manager bundle activate $candidate_bundle --state-root $candidate_state >/dev/null

managed_child() {
  builtin cd -q -- $fixture
  export HOME=$home TERM=xterm-256color
  unset ZDOTDIR WSH_BUNDLE_ROOT WSH_USER_ZDOTDIR WSH_RUN_FOREGROUND WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  command stty -echo
  if [[ $current_build == baseline ]]; then
    exec taskset -c $cpu $baseline_manager run --state-root $baseline_state
  fi
  exec taskset -c $cpu $candidate_manager run --state-root $candidate_state
}

measure() {
  local build=$1 block=$2 position=$3 repetition=$4 chunk
  local -F started=$EPOCHREALTIME editable_at
  current_build=$build
  current_pty=wsh_managed_build_${build}_${block}_${repetition}_${$}
  zpty -b $current_pty managed_child
  zpty -r -m $current_pty chunk $'*\e]133;B*' || {
    print -u2 -r -- "shell exited before its editable prompt for ${build}: ${(qqq)chunk}"
    return 1
  }
  editable_at=$EPOCHREALTIME
  printf '%s\t%s\t%d\t%s\t%d\t%.6f\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $block $position $build $repetition \
    $(( (editable_at - started) * 1000 )) >> $staging
  zpty -w $current_pty exit
  zpty -d $current_pty 2>/dev/null || true
  current_pty=
}

print -r -- $'measured_at_utc\tblock\tposition\tbuild\trepetition\tfirst_editable_ms' > $staging
local build block position repetition
for repetition in {1..$warmups}; do
  measure baseline warmup 1 $repetition
  measure candidate warmup 2 $repetition
done
command sed -i '/\twarmup\t/d' $staging

local -a order
for block in forward reverse; do
  if [[ $block == forward ]]; then
    order=(baseline candidate)
  else
    order=(candidate baseline)
  fi
  for repetition in {1..$repetitions}; do
    position=0
    for build in $order; do
      (( position += 1 ))
      measure $build $block $position $repetition
    done
  done
done

mv -- $staging $output
trap - EXIT INT TERM
command rm -rf -- $scratch
print -r -- $output
