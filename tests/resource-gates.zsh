#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

local root=${0:A:h:h}
local scratch
scratch=$(mktemp -d /var/tmp/wsh-resource-gates.XXXXXX)
trap 'command rm -rf -- $scratch' EXIT INT TERM

write_trace() {
  local file=$1 overhead=$2
  print -r -- $'state\titeration\torder\tplain_ready_us\ttraced_ready_us\tready_overhead_us\tplain_refresh_us\ttraced_refresh_us\trefresh_overhead_us' > $file
  local state order
  local -i iteration
  for state in clean dirty untracked; do
    for (( iteration = 1; iteration <= 20; ++iteration )); do
      (( iteration % 2 )) && order=plain-first || order=traced-first
      printf '%s\t%d\t%s\t1000\t%d\t%d\t7000\t%d\t%d\n' $state $iteration $order $(( 1000 + overhead )) $overhead $(( 7000 + overhead )) $overhead >> $file
    done
  done
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

write_trace $scratch/trace.tsv 400
write_memory $scratch/memory.tsv 4000
$root/benchmarks/check-resource-gates.zsh $scratch/memory.tsv $scratch/trace.tsv > $scratch/pass.tsv
[[ $(tail -n +2 $scratch/pass.tsv | cut -f4 | sort -u) == pass ]] || return 1

write_memory $scratch/memory.tsv 6000
if $root/benchmarks/check-resource-gates.zsh $scratch/memory.tsv $scratch/trace.tsv > $scratch/fail.tsv; then
  print -u2 -- 'resource gate checker accepted excessive memory'
  return 1
fi
[[ $(command awk -F '\t' '$1 == "retained-added-pss-max-kib" { print $4 }' $scratch/fail.tsv) == fail ]] || return 1

write_memory $scratch/memory.tsv 4000
write_trace $scratch/trace.tsv 600
if $root/benchmarks/check-resource-gates.zsh $scratch/memory.tsv $scratch/trace.tsv > $scratch/fail.tsv; then
  print -u2 -- 'resource gate checker accepted excessive trace overhead'
  return 1
fi
[[ $(command awk -F '\t' '$1 == "trace-refresh-p90-overhead-ms" { print $4 }' $scratch/fail.tsv) == fail ]] || return 1

print -r -- 'PASS: resource gate checker accepts bounded measurements and rejects an exceeded threshold'
