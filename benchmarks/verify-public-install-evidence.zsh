#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly repository_root=${0:A:h:h}
readonly evidence=${repository_root}/benchmarks/public-install-v0.1.1-2026-09-03
readonly metadata=${evidence}/metadata.txt

metadata_value() {
  local key=$1
  sed -n "s/^${key}=//p" $metadata
}

verify_hash() {
  local key=$1
  local input_file=$2
  local actual=$(sha256sum $input_file)
  [[ ${actual%% *} == $(metadata_value $key) ]] || {
    print -u2 -- "error: retained public-install evidence hash mismatch: $key"
    exit 1
  }
}

summarize() {
  local input_file=$1 column=$2
  awk -F '\t' -v column=$column 'NR > 1 { print $column }' $input_file \
    | sort -n \
    | awk '{ a[++n]=$1 } END { p90=int((n*90+99)/100); if (n%2) median=a[(n+1)/2]; else median=(a[n/2]+a[n/2+1])/2; printf "%d\t%.3f\t%.3f\t%.3f", n, median, a[p90], a[n] }'
}

verify_sample() {
  local input_file=$1 expected_environment=$2
  awk -F '\t' -v expected_environment=$expected_environment '
    NR == 1 {
      expected="measured_at_utc\tenvironment\tphase\trepetition\tbootstrap_fetch_ms\tbootstrap_execution_ms\tfirst_prompt_ms\ttotal_ms"
      if ($0 != expected) exit 1
      next
    }
    $2 != expected_environment || $3 != "measured" || $4 !~ /^[0-9]+$/ || seen[$4]++ || $5 <= 0 || $6 <= 0 || $7 <= 0 || $8 <= 0 { exit 1 }
    { count++ }
    END { if (count != 10) exit 1 }
  ' $input_file || {
    print -u2 -- "error: invalid retained public-install sample: ${input_file:t}"
    exit 1
  }
}

readonly fedora=${evidence}/fedora.tsv
readonly rocky=${evidence}/rocky.tsv
verify_hash fedora_samples_sha256 $fedora
verify_hash rocky_samples_sha256 $rocky
verify_hash benchmark_sha256 ${repository_root}/benchmarks/benchmark-public-install.zsh
verify_hash plan_sha256 ${repository_root}/benchmarks/public-install-v0.1.1-plan-2026-09-03.md
verify_sample $fedora fedora-44
verify_sample $rocky rocky-8.10-glibc-2.28

[[ $(summarize $fedora 5) == $'10\t104.160\t126.642\t166.363' ]]
[[ $(summarize $fedora 6) == $'10\t1555.291\t1636.134\t1853.750' ]]
[[ $(summarize $fedora 7) == $'10\t8.883\t9.130\t9.142' ]]
[[ $(summarize $fedora 8) == $'10\t1666.643\t1756.501\t2028.953' ]]
[[ $(summarize $rocky 5) == $'10\t117.127\t133.203\t138.553' ]]
[[ $(summarize $rocky 6) == $'10\t963.429\t1001.962\t1035.045' ]]
[[ $(summarize $rocky 7) == $'10\t8.244\t8.446\t8.492' ]]
[[ $(summarize $rocky 8) == $'10\t1098.486\t1115.246\t1149.717' ]]

awk -v fedora_total=1756.501 -v rocky_total=1115.246 -v fedora_prompt=9.130 -v rocky_prompt=8.446 \
  'BEGIN { exit ! (fedora_total <= 5000 && rocky_total <= 5000 && fedora_prompt <= 50 && rocky_prompt <= 50) }'

print -r -- 'PASS: retained public-install inputs, summaries, and fixed gates agree'
