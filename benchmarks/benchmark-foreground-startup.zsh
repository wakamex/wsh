#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent
zmodload zsh/datetime zsh/zpty

(( $# == 4 )) || {
  print -u2 -- 'usage: benchmark-foreground-startup.zsh OUTPUT MANAGER BUNDLE PROBE-SOURCE'
  exit 2
}

readonly output=${1:A}
readonly manager=${2:A}
readonly bundle=${3:A}
readonly probe_source=${4:A}
readonly repetitions=20
readonly warmups=5
readonly cpu=${WSH_FOREGROUND_CPU:-0}
readonly test_root=$(mktemp -d /var/tmp/wsh-foreground-benchmark.XXXXXX)
readonly staging=$(mktemp "${output:h}/.${output:t}.XXXXXX")
readonly probe=$test_root/foreground-probe
readonly home=$test_root/home
readonly fixture=$test_root/fixture
readonly state_root=$test_root/state
typeset -g current_pty= current_variant= pty_output=

[[ ! -e $output && ! -L $output && -x $manager && -x $bundle/bin/zsh && -f $probe_source ]] || {
  print -u2 -- 'error: output must be new and manager, bundle, and probe source must exist'
  exit 2
}

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $staging $test_root
}
trap cleanup EXIT INT TERM

command gcc -std=c11 -O2 -Wall -Wextra -Werror $probe_source -o $probe
command mkdir -p -- $home $fixture
print -r -- 'typeset -g WSH_DISABLE_HISTORY_SUBSTRING_SEARCH=1
typeset -g WSH_DISABLE_AUTOSUGGESTIONS=1
typeset -g WSH_DISABLE_SYNTAX_HIGHLIGHTING=1' >| $home/.zshrc
git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh foreground benchmark'
git -C $fixture config user.email foreground-benchmark@wsh.invalid
print -r -- tracked > $fixture/tracked
git -C $fixture add tracked
git -C $fixture commit -qm initial
$manager bundle activate $bundle --state-root $state_root >/dev/null

benchmark_child() {
  builtin cd -q -- $fixture
  export HOME=$home ZDOTDIR=$bundle/share/wsh/zdotdir WSH_USER_ZDOTDIR=$home
  export WSH_BUNDLE_ROOT=$bundle WSH_RUNTIME=$bundle/bin/wsh-runtime
  export WSH_THEME=$bundle/share/wsh/themes/minimal.toml TERM=xterm-256color
  unset WSH_RUN_FOREGROUND WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  command stty -echo
  local report=$test_root/${current_variant}-${RANDOM}.report
  case $current_variant in
    current)
      local invocation="${probe} ${report} exit0"
      exec taskset -c $cpu $bundle/bin/zsh -d -l -i -c "${invocation}; exec \"\$0\" -d -l -i" $bundle/bin/zsh
      ;;
    positional)
      exec taskset -c $cpu $bundle/bin/zsh -d -l -i -c '"$@"; exec "$0" -d -l -i' $bundle/bin/zsh $probe $report exit0
      ;;
    candidate)
      exec taskset -c $cpu $manager run-foreground --state-root $state_root --login -- $probe $report exit0
      ;;
  esac
}

measure() {
  local variant=$1 block=$2 position=$3 repetition=$4
  current_variant=$variant
  current_pty=wsh_foreground_bench_${variant}_${block}_${repetition}_${$}
  pty_output=
  local -F started=$EPOCHREALTIME ready_at=0 prompt_at=0
  local chunk
  zpty -b $current_pty benchmark_child
  zpty -r -m $current_pty chunk '*WSH_FOREGROUND_READY*' || {
    print -u2 -r -- "foreground process exited before readiness for ${variant}: ${(qqq)chunk}"
    return 1
  }
  pty_output+=$chunk
  ready_at=$EPOCHREALTIME
  zpty -r -m $current_pty chunk $'*\e]133;B*' || {
    print -u2 -r -- "shell exited before its editable prompt for ${variant}: ${(qqq)chunk}"
    return 1
  }
  pty_output+=$chunk
  prompt_at=$EPOCHREALTIME
  printf '%s\t%s\t%d\t%s\t%d\t%.6f\t%.6f\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $block $position $variant $repetition \
    $(( (ready_at - started) * 1000 )) $(( (prompt_at - ready_at) * 1000 )) >> $staging
  zpty -w $current_pty exit
  zpty -d $current_pty 2>/dev/null || true
  current_pty=
}

print -r -- $'measured_at_utc\tblock\tposition\tvariant\trepetition\tpty_to_ready_ms\tready_to_prompt_ms' > $staging
local variant repetition block position
for variant in current positional candidate; do
  for repetition in {1..$warmups}; do
    measure $variant warmup 0 $repetition
  done
done
command sed -i '/\twarmup\t/d' $staging

local -a order
for block in forward reverse; do
  if [[ $block == forward ]]; then
    order=(current positional candidate)
  else
    order=(candidate positional current)
  fi
  position=0
  for variant in $order; do
    (( position += 1 ))
    for repetition in {1..$repetitions}; do
      measure $variant $block $position $repetition
    done
  done
done

mv -- $staging $output
trap - EXIT INT TERM
command rm -rf -- $test_root
print -r -- $output
