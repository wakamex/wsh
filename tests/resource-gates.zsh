#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

local root=${0:A:h:h}
local scratch
scratch=$(mktemp -d /var/tmp/wsh-resource-gates.XXXXXX)
trap 'command rm -rf -- $scratch' EXIT INT TERM

write_trace_run() {
  local directory=$1 targets=$2 first_delta=$3 settled_delta=$4
  command mkdir -p $directory
  print -r -- $'accepted=1\niterations=20\ntargets='${targets} > $directory/metadata.txt
  print -r -- $'target\tstate\tsamples\tfirst_median_ms\tfirst_p10_ms\tfirst_p90_ms\tfirst_max_ms\tsettled_median_ms\tsettled_p10_ms\tsettled_p90_ms\tsettled_max_ms\trepaints_median\tgit_calls_median\tunlocked_calls_median\tsemantic_passes' > $directory/distribution.tsv
  local state
  for state in clean dirty untracked; do
    printf '%s\t%s\t20\t1.0\t0.9\t1.0\t1.1\t7.0\t6.8\t7.0\t7.2\t1.000\t1.000\t0.000\t20/20\n' wsh $state >> $directory/distribution.tsv
    printf '%s\t%s\t20\t1.0\t0.9\t%.3f\t1.1\t7.0\t6.8\t%.3f\t7.2\t1.000\t1.000\t0.000\t20/20\n' wsh-trace $state $(( 1.0 + first_delta )) $(( 7.0 + settled_delta )) >> $directory/distribution.tsv
  done
  print -r -- $'a\tb\ttarget\tstaged\tdetached' > $directory/summary.tsv
  print -r -- $'x\tx\twsh\t1\t1' >> $directory/summary.tsv
  print -r -- $'x\tx\twsh-trace\t1\t1' >> $directory/summary.tsv
}

write_memory() {
  local file=$1 value=$2
  print -r -- $'iteration\torder\traw_zsh_pss_kib\twsh_zsh_pss_kib\twsh_runtime_pss_kib\twsh_combined_pss_kib\tadded_pss_kib' > $file
  local -i iteration
  local order
  for (( iteration = 1; iteration <= 20; ++iteration )); do
    (( iteration % 2 )) && order=raw-first || order=wsh-first
    printf '%d\t%s\t1000\t1500\t%d\t%d\t%d\n' $iteration $order $(( value - 500 )) $(( value + 1000 )) $value >> $file
  done
}

write_trace_run $scratch/forward wsh,wsh-trace 0.400 0.400
write_trace_run $scratch/reverse wsh-trace,wsh 0.400 0.400
write_memory $scratch/memory.tsv 4000
$root/benchmarks/check-resource-gates.zsh $scratch/memory.tsv $scratch/forward $scratch/reverse > $scratch/pass.tsv
[[ $(tail -n +2 $scratch/pass.tsv | cut -f4 | sort -u) == pass ]] || return 1

write_memory $scratch/memory.tsv 6000
if $root/benchmarks/check-resource-gates.zsh $scratch/memory.tsv $scratch/forward $scratch/reverse > $scratch/fail.tsv; then
  print -u2 -- 'resource gate checker accepted excessive memory'
  return 1
fi
[[ $(command awk -F '\t' '$1 == "retained-added-pss-max-kib" { print $4 }' $scratch/fail.tsv) == fail ]] || return 1

print -r -- 'PASS: resource gate checker accepts bounded measurements and rejects an exceeded threshold'
