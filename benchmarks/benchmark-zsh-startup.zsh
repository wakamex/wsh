#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

usage() {
  print -r -- 'usage: benchmark-zsh-startup.zsh OUTPUT LABEL=ZSH [LABEL=ZSH]...'
}

(( $# >= 2 )) || {
  usage >&2
  exit 2
}

readonly output=${1:A}
shift
[[ ! -e $output && ! -L $output ]] || {
  print -u2 -- "error: output already exists: $output"
  exit 1
}

for command in awk date mktemp mv rm taskset time zsh; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done

local -a labels=() binaries=()
local specification label binary
for specification in "$@"; do
  [[ $specification == *=* ]] || {
    print -u2 -- "error: expected LABEL=ZSH: $specification"
    exit 2
  }
  label=${specification%%=*}
  binary=${specification#*=}
  [[ -n $label && -x $binary ]] || {
    print -u2 -- "error: invalid Zsh specification: $specification"
    exit 2
  }
  labels+=($label)
  binaries+=(${binary:A})
done

readonly launches=5000
readonly repetitions=5
readonly warmup_launches=200
readonly cpu=${WSH_STARTUP_BENCHMARK_CPU:-0}
local staging timing
staging=$(mktemp "${output:h}/.${output:t}.XXXXXX")
timing=$(mktemp /tmp/wsh-startup-time.XXXXXX)
trap 'rm -f -- $staging $timing' EXIT INT TERM

print -r -- $'measured_at_utc\tblock\tposition\tvariant\trepetition\tlaunches\telapsed_seconds\tuser_seconds\tsystem_seconds\tmean_elapsed_us' > $staging

local index block position repetition elapsed user system mean
for index in {1..${#labels}}; do
  taskset -c $cpu zsh -fc 'repeat $1; do "$2" -f -c exit; done' -- $warmup_launches $binaries[$index]
done

for block in forward reverse; do
  local -a order
  if [[ $block == forward ]]; then
    order=({1..${#labels}})
  else
    order=({${#labels}..1})
  fi
  position=0
  for index in $order; do
    (( position += 1 ))
    for repetition in {1..$repetitions}; do
      /usr/bin/time -f $'%e\t%U\t%S' -o $timing \
        taskset -c $cpu zsh -fc 'repeat $1; do "$2" -f -c exit; done' -- $launches $binaries[$index]
      IFS=$'\t' read -r elapsed user system < $timing
      mean=$(awk -v elapsed=$elapsed -v launches=$launches 'BEGIN { printf "%.3f", elapsed * 1000000 / launches }')
      print -r -- "$(date -u +%Y-%m-%dT%H:%M:%SZ)\t${block}\t${position}\t${labels[$index]}\t${repetition}\t${launches}\t${elapsed}\t${user}\t${system}\t${mean}" >> $staging
    done
  done
done

mv -- $staging $output
trap - EXIT INT TERM
rm -f -- $timing
print -r -- $output
