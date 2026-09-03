#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly repository_root=${0:A:h:h}
readonly evidence=${repository_root}/benchmarks/runtime-job-announcement-2026-09-03
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
    print -u2 -- "error: retained runtime-job evidence hash mismatch: $key"
    exit 1
  }
}

verify_git_object_hash() {
  local key=$1
  local revision=$2
  local input_path=$3
  local actual=$(git show ${revision}:${input_path} | sha256sum)
  [[ ${actual%% *} == $(metadata_value $key) ]] || {
    print -u2 -- "error: retained runtime-job source hash mismatch: $key"
    exit 1
  }
}

verify_sample() {
  local input_file=$1
  awk -F '\t' '
    NR == 1 {
      expected="measured_at_utc\tblock\tposition\tvariant\trepetition\tfirst_editable_ms"
      if ($0 != expected) exit 1
      next
    }
    {
      if ($1 == "" || ($2 != "forward" && $2 != "reverse") || $3 !~ /^[1-3]$/ || ($4 != "raw" && $4 != "direct-complete" && $4 != "managed-complete") || $5 !~ /^[0-9]+$/ || $5 < 1 || $5 > 20 || $6 <= 0) exit 1
      expected_position = ($2 == "forward" ? ($4 == "raw" ? 1 : ($4 == "direct-complete" ? 2 : 3)) : ($4 == "managed-complete" ? 1 : ($4 == "direct-complete" ? 2 : 3)))
      if ($3 != expected_position || seen[$2 SUBSEP $4 SUBSEP $5]++) exit 1
      count[$4]++
    }
    END {
      if (count["raw"] != 40 || count["direct-complete"] != 40 || count["managed-complete"] != 40) exit 1
    }
  ' $input_file || {
    print -u2 -- "error: invalid retained runtime-job sample: ${input_file:t}"
    exit 1
  }
}

summarize() {
  local input_file=$1 variant=$2
  awk -F '\t' -v variant=$variant 'NR > 1 && $4 == variant { print $6 }' $input_file \
    | sort -n \
    | awk '{ a[++n]=$1 } END { p90=int((n*90+99)/100); if (n%2) median=a[(n+1)/2]; else median=(a[n/2]+a[n/2+1])/2; printf "%d\t%.3f\t%.3f\t%.3f", n, median, a[p90], a[n] }'
}

readonly release=${evidence}/release.tsv
readonly fixed=${evidence}/fixed.tsv
readonly release_cpu0=${evidence}/release-cpu0.tsv
readonly fixed_cpu0_failed=${evidence}/fixed-cpu0-failed.tsv
verify_hash release_samples_sha256 $release
verify_hash fixed_samples_sha256 $fixed
verify_hash release_cpu0_samples_sha256 $release_cpu0
verify_hash fixed_cpu0_failed_samples_sha256 $fixed_cpu0_failed
readonly fixed_source_revision=$(metadata_value fixed_source_revision)
verify_git_object_hash benchmark_sha256 $fixed_source_revision benchmarks/benchmark-first-editable.zsh
verify_git_object_hash plan_sha256 $fixed_source_revision benchmarks/runtime-job-announcement-plan-2026-09-03.md
verify_sample $release
verify_sample $fixed
verify_sample $release_cpu0
verify_sample $fixed_cpu0_failed

[[ $(summarize $release raw) == $'40\t5.054\t5.793\t6.406' ]]
[[ $(summarize $release direct-complete) == $'40\t7.243\t7.976\t9.486' ]]
[[ $(summarize $release managed-complete) == $'40\t8.076\t9.443\t10.883' ]]
[[ $(summarize $fixed raw) == $'40\t4.968\t5.119\t5.453' ]]
[[ $(summarize $fixed direct-complete) == $'40\t7.142\t7.313\t7.416' ]]
[[ $(summarize $fixed managed-complete) == $'40\t7.806\t7.987\t8.870' ]]
[[ $(summarize $release_cpu0 raw) == $'40\t5.061\t5.280\t6.672' ]]
[[ $(summarize $release_cpu0 direct-complete) == $'40\t7.430\t7.644\t9.459' ]]
[[ $(summarize $release_cpu0 managed-complete) == $'40\t8.016\t8.431\t8.938' ]]
[[ $(summarize $fixed_cpu0_failed raw) == $'40\t5.240\t6.343\t7.182' ]]
[[ $(summarize $fixed_cpu0_failed direct-complete) == $'40\t7.915\t8.691\t9.769' ]]
[[ $(summarize $fixed_cpu0_failed managed-complete) == $'40\t8.457\t9.863\t10.834' ]]

awk -v raw_p90=5.119085 -v raw_max=5.453348 -v direct_p90=7.313013 -v managed_p90=7.986546 -v managed_max=8.870125 \
  'BEGIN { exit ! (managed_p90 - raw_p90 <= 5.0 && managed_max - raw_max <= 8.0 && managed_p90 - direct_p90 <= 1.0) }'

print -r -- 'PASS: retained runtime-job inputs, summaries, and fixed gates agree'
