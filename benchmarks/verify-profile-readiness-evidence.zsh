#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
readonly root=${0:A:h:h}
readonly evidence=$root/benchmarks/profile-readiness-2026-09-05
readonly scratch=$(mktemp -d /var/tmp/wsh-profile-readiness-evidence.XXXXXX)
trap 'command rm -rf -- $scratch' EXIT INT TERM
builtin cd -- $root
sha256sum -c $evidence/SHA256SUMS >/dev/null
$root/benchmarks/summarize-profile.zsh $evidence/native-samples.tsv $scratch/summary.tsv >/dev/null
$root/benchmarks/check-profile-gates.zsh $scratch/summary.tsv $root/benchmarks/profile-2026-09-05/runtime-trace.tsv > $scratch/gates.tsv
diff -u $evidence/native-summary.tsv $scratch/summary.tsv
diff -u $evidence/gates.tsv $scratch/gates.tsv
[[ $(awk -F '\t' 'NR>1 { n++ } END { print n }' $evidence/native-samples.tsv) == 200 ]]
[[ $(awk -F '\t' '$1=="first-editable-overhead" { print $3 }' $evidence/native-summary.tsv) == 100 ]]
[[ $(grep -c 'omitted the 200 ms editor-init delay' $evidence/delayed-visible-control.log) == 4 ]]
grep -q '^PASS: readiness waits for delayed ZLE initialization' $evidence/delayed-native.log
grep -q '^PASS: private end-to-end profile' $evidence/profile-correctness.log
print -r -- 'PASS: native editor-readiness samples, fixed gates, delayed-hook regression and source hashes agree'
