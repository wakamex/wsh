#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
readonly root=${0:A:h:h}
readonly evidence=$root/benchmarks/prompt-ownership-2026-09-05
readonly scratch=$(mktemp -d /var/tmp/wsh-prompt-evidence.XXXXXX)
trap 'command rm -rf -- $scratch' EXIT INT TERM
builtin cd -- $root
sha256sum -c $evidence/SHA256SUMS >/dev/null
$root/benchmarks/summarize-profile.zsh $evidence/profile-samples.tsv $scratch/summary.tsv >/dev/null
$root/benchmarks/check-profile-gates.zsh $scratch/summary.tsv $root/benchmarks/profile-2026-09-05/runtime-trace.tsv > $scratch/gates.tsv
diff -u $evidence/profile-summary.tsv $scratch/summary.tsv
diff -u $evidence/profile-gates.tsv $scratch/gates.tsv
[[ $(awk -F '\t' '$1=="first-editable-overhead" { print $3 }' $scratch/summary.tsv) == 100 ]]
[[ $(grep -c '^PASS: .*prompt ownership' $evidence/correctness.log) == 12 ]]
[[ $(grep -c '^PASS: .*prompt ownership' $evidence/omz-correctness.log) == 12 ]]
grep -q '^PASS: real OMZ overlap advice' $evidence/omz-correctness.log
grep -q '^PASS: structured foreground startup' $evidence/foreground-existing.log
print -r -- 'PASS: prompt ownership evidence hashes, 24 shared-configuration cases, OMZ advice, foreground checks and 100-pair profiling gate agree'
