#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
(( $# == 2 || $# == 3 )) || {
  print -u2 -- 'usage: profile-readiness.zsh MANAGER BUNDLE [BENCHMARK]'
  exit 2
}
readonly manager=${1:A}
readonly bundle=${2:A}
readonly root=${0:A:h:h}
readonly benchmark=${3:-$root/benchmarks/benchmark-profile.zsh}
readonly scratch=$(mktemp -d /var/tmp/wsh-profile-readiness-test.XXXXXX)
trap 'command rm -rf -- $scratch' EXIT INT TERM

cat > $scratch/delayed.zshrc <<'FIXTURE'
# Prompt-like output and a visible prompt both precede editor initialization.
print -rn -- 'startup % '
autoload -Uz add-zsh-hook add-zle-hook-widget
_wsh_readiness_delay() { zmodload zsh/zselect; zselect -t 20 2>/dev/null || true; }
_wsh_readiness_install() {
  zmodload zsh/zle
  add-zle-hook-widget zle-line-init _wsh_readiness_delay
  add-zsh-hook -d precmd _wsh_readiness_install
}
add-zsh-hook precmd _wsh_readiness_install
FIXTURE

WSH_PROFILE_BENCH_ZSHRC=$scratch/delayed.zshrc \
  zsh $benchmark $scratch/samples.tsv $manager $bundle 1 >/dev/null
command cat -- $scratch/samples.tsv
awk -F '\t' '
  NR > 1 {
    count++
    if ($6 < 200 || $7 < $6) {
      printf "FAIL: %s readiness %.3f ms omitted the 200 ms editor-init delay\n", $4, $6 > "/dev/stderr"
      failed = 1
    }
  }
  END { exit (count != 4 || failed) }
' $scratch/samples.tsv
print -r -- 'PASS: readiness waits for delayed ZLE initialization in normal and profiled shells and ignores earlier prompt-like output'
