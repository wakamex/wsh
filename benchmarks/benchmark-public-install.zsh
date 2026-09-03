#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
zmodload zsh/datetime zsh/zpty zsh/zselect

usage() {
  print -r -- 'usage: benchmark-public-install.zsh OUTPUT ENVIRONMENT_LABEL RELEASE_TAG SOURCE_COMMIT [ITERATIONS]'
}

(( $# >= 4 && $# <= 5 )) || {
  usage >&2
  exit 2
}

readonly output=${1:A}
readonly environment_label=$2
readonly release_tag=$3
readonly source_commit=$4
readonly iterations=${5:-10}
readonly bootstrap_url=https://github.com/wakamex/wsh/releases/download/${release_tag}/wsh-${release_tag}-install.sh

[[ $environment_label =~ '^[A-Za-z0-9._-]+$' ]] || {
  print -u2 -- 'error: environment label must contain only letters, digits, dots, underscores, or hyphens'
  exit 2
}
[[ $release_tag =~ '^v[0-9]+\.[0-9]+\.[0-9]+$' ]] || {
  print -u2 -- 'error: release tag must be canonical vMAJOR.MINOR.PATCH'
  exit 2
}
[[ $source_commit =~ '^[0-9a-f]{40}$' ]] || {
  print -u2 -- 'error: source commit must be lowercase 40-hex'
  exit 2
}
[[ $iterations == <1-> ]] || {
  print -u2 -- 'error: iterations must be a positive integer'
  exit 2
}
[[ ! -e $output && ! -L $output ]] || {
  print -u2 -- "error: output already exists: $output"
  exit 1
}

for command in curl date jq mkdir mktemp mv rm sed sha256sum taskset uname; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done

readonly cpu=${WSH_PUBLIC_INSTALL_CPU:-0}
local staging scratch current_root current_pty= pty_output=
staging=$(mktemp "${output:h}/.${output:t}.XXXXXX")
scratch=$(mktemp -d /var/tmp/wsh-public-install.XXXXXX)

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $staging $scratch
}
trap cleanup EXIT INT TERM

first_prompt_child() {
  builtin cd -q -- $current_root/home
  export HOME=$current_root/home
  export WSH_STATE_ROOT=$current_root/state
  export TERM=xterm-256color
  command stty -echo
  exec taskset -c $cpu $current_root/bin/wsh run
}

wait_for_first_prompt() {
  local chunk
  local -F started=$EPOCHREALTIME deadline=$(( EPOCHREALTIME + 5 ))
  pty_output=
  current_pty=wsh_public_install_${$}_${RANDOM}
  zpty -b $current_pty first_prompt_child
  local pty_fd=$REPLY
  while (( EPOCHREALTIME < deadline )); do
    while zpty -r -t $current_pty chunk 2>/dev/null; do
      pty_output+=$chunk
      if [[ $pty_output == *'% '* || $pty_output == *'# '* ]]; then
        REPLY=$(( (EPOCHREALTIME - started) * 1000 ))
        zpty -w $current_pty exit
        zselect -r $pty_fd -t 100 2>/dev/null || true
        zpty -d $current_pty 2>/dev/null || true
        current_pty=
        return 0
      fi
    done
    zselect -r $pty_fd -t 1 2>/dev/null || true
  done
  print -u2 -r -- "error: timeout waiting for installed prompt: ${(qqq)pty_output}"
  return 1
}

run_observation() {
  local phase=$1 repetition=$2
  current_root=$scratch/${phase}-${repetition}
  command mkdir -p -- $current_root/home $current_root/bin $current_root/libexec $current_root/state
  local bootstrap=$current_root/install.sh
  local install_log=$current_root/install.log
  local -F started=$EPOCHREALTIME fetched installed prompt_ms fetch_ms install_ms total_ms

  command curl --disable --proto '=https' --proto-redir '=https' --tlsv1.2 --fail --location --retry 3 --silent --show-error --output $bootstrap $bootstrap_url
  fetched=$EPOCHREALTIME
  HOME=$current_root/home \
  WSH_BIN_DIR=$current_root/bin \
  WSH_LIBEXEC_DIR=$current_root/libexec \
  WSH_STATE_ROOT=$current_root/state \
    command sh $bootstrap >$install_log 2>&1
  installed=$EPOCHREALTIME

  wait_for_first_prompt
  prompt_ms=$REPLY

  local bundle=$($current_root/bin/wsh bundle current --state-root $current_root/state)
  [[ -d $bundle && ! -L $bundle ]] || {
    print -u2 -- "error: installed bundle is missing or unsafe: $bundle"
    return 1
  }
  command jq -e --arg tag $release_tag --arg commit $source_commit \
    '.status == "release" and .release_id == $tag and .rust.source_revision == $commit' \
    $bundle/manifest.json >/dev/null || {
      print -u2 -- 'error: installed bundle identity does not match the official release'
      return 1
    }

  fetch_ms=$(( (fetched - started) * 1000 ))
  install_ms=$(( (installed - fetched) * 1000 ))
  total_ms=$(( fetch_ms + install_ms + prompt_ms ))
  printf '%s\t%s\t%s\t%d\t%.6f\t%.6f\t%.6f\t%.6f\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $environment_label $phase $repetition \
    $fetch_ms $install_ms $prompt_ms $total_ms >> $staging
}

print -r -- $'measured_at_utc\tenvironment\tphase\trepetition\tbootstrap_fetch_ms\tbootstrap_execution_ms\tfirst_prompt_ms\ttotal_ms' > $staging
run_observation warmup 1

local repetition
for repetition in {1..$iterations}; do
  run_observation measured $repetition
done

command sed -i '/\twarmup\t/d' $staging
command mv -- $staging $output
trap - EXIT INT TERM
command rm -rf -- $scratch
print -r -- $output
