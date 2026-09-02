#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

usage() {
  print -r -- 'usage: benchmark-manager-launch.zsh OUTPUT MANAGER BUNDLE'
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
[[ -x $manager && -d $bundle ]] || {
  print -u2 -- 'error: manager and bundle must exist'
  exit 2
}

for command in awk date mktemp mv taskset time zsh; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done

readonly launches=100
readonly repetitions=5
readonly warmup_launches=20
readonly cpu=${WSH_MANAGER_BENCHMARK_CPU:-0}
local staging timing state_root
staging=$(mktemp "${output:h}/.${output:t}.XXXXXX")
timing=$(mktemp /tmp/wsh-manager-time.XXXXXX)
state_root=$(mktemp -d /tmp/wsh-manager-state.XXXXXX)
trap 'rm -rf -- $staging $timing $state_root' EXIT INT TERM

$manager bundle activate $bundle --state-root $state_root >/dev/null

print -r -- $'measured_at_utc\tblock\tposition\tvariant\trepetition\tlaunches\telapsed_seconds\tuser_seconds\tsystem_seconds\tmean_elapsed_us' > $staging

run_variant() {
  local variant=$1 block=$2 position=$3 repetition=$4 elapsed user system mean
  case $variant in
    direct)
      /usr/bin/time -f $'%e\t%U\t%S' -o $timing \
        taskset -c $cpu zsh -fc 'repeat $1; do "$2" -f -c exit; done' -- $launches $bundle/bin/zsh
      ;;
    managed)
      /usr/bin/time -f $'%e\t%U\t%S' -o $timing \
        taskset -c $cpu zsh -fc 'repeat $1; do "$2" run --state-root "$3" -- -f -c exit; done' -- $launches $manager $state_root
      ;;
    *)
      print -u2 -- "error: unknown variant: $variant"
      return 1
      ;;
  esac
  IFS=$'\t' read -r elapsed user system < $timing
  mean=$(awk -v elapsed=$elapsed -v launches=$launches 'BEGIN { printf "%.3f", elapsed * 1000000 / launches }')
  printf '%s\t%s\t%d\t%s\t%d\t%d\t%s\t%s\t%s\t%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $block $position $variant $repetition \
    $launches $elapsed $user $system $mean >> $staging
}

taskset -c $cpu zsh -fc 'repeat $1; do "$2" -f -c exit; done' -- $warmup_launches $bundle/bin/zsh
taskset -c $cpu zsh -fc 'repeat $1; do "$2" run --state-root "$3" -- -f -c exit; done' -- $warmup_launches $manager $state_root

local block position repetition variant
local -a order
for block in forward reverse; do
  if [[ $block == forward ]]; then
    order=(direct managed)
  else
    order=(managed direct)
  fi
  position=0
  for variant in $order; do
    (( position += 1 ))
    for repetition in {1..$repetitions}; do
      run_variant $variant $block $position $repetition
    done
  done
done

mv -- $staging $output
trap - EXIT INT TERM
rm -rf -- $timing $state_root
print -r -- $output
