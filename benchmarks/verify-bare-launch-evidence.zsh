#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly repository_root=${0:A:h:h}
readonly evidence=${repository_root}/benchmarks/bare-launch-2026-09-03
readonly metadata=${evidence}/metadata.txt
readonly samples=${evidence}/startup.tsv

metadata_value() {
  local key=$1
  sed -n "s/^${key}=//p" $metadata
}

verify_hash() {
  local key=$1
  local input_file=$2
  local actual=$(sha256sum $input_file)
  [[ ${actual%% *} == $(metadata_value $key) ]] || {
    print -u2 -- "error: retained bare-launch evidence hash mismatch: $key"
    exit 1
  }
}

verify_git_object_hash() {
  local key=$1
  local revision=$2
  local input_path=$3
  local actual=$(git show ${revision}:${input_path} | sha256sum)
  [[ ${actual%% *} == $(metadata_value $key) ]] || {
    print -u2 -- "error: retained bare-launch source hash mismatch: $key"
    exit 1
  }
}

summarize_variant() {
  local variant=$1
  awk -F '\t' -v variant=$variant 'NR > 1 && $4 == variant { print $6 }' $samples \
    | sort -n \
    | awk 'BEGIN { n=0 } { a[++n]=$1 } END { p90=int((n*90+99)/100); if (n%2) median=a[(n+1)/2]; else median=(a[n/2]+a[n/2+1])/2; printf "%d\t%.6f\t%.6f\t%.6f", n, median, a[p90], a[n] }'
}

verify_hash samples_sha256 $samples
readonly source_revision=$(metadata_value source_revision)
verify_git_object_hash manager_main_sha256 $source_revision crates/wsh/src/main.rs
verify_git_object_hash benchmark_sha256 $source_revision benchmarks/benchmark-first-editable.zsh
verify_git_object_hash plan_sha256 $source_revision benchmarks/bare-launch-plan-2026-09-03.md
verify_git_object_hash floor_test_sha256 $source_revision build/test-development-bundle.zsh
verify_git_object_hash validation_workflow_sha256 $source_revision .github/workflows/validation.yml

readonly raw=$(summarize_variant raw)
readonly direct=$(summarize_variant direct-complete)
readonly managed=$(summarize_variant managed-complete)
[[ $raw == $'40\t4.935384\t5.050659\t5.162239' ]] || {
  print -u2 -- "error: retained raw startup summary changed: $raw"
  exit 1
}
[[ $direct == $'40\t7.276058\t7.444620\t7.759333' ]] || {
  print -u2 -- "error: retained direct startup summary changed: $direct"
  exit 1
}
[[ $managed == $'40\t7.798910\t7.989883\t8.242607' ]] || {
  print -u2 -- "error: retained managed startup summary changed: $managed"
  exit 1
}

awk 'BEGIN { exit !((7.989883 - 5.050659 <= 5.0) && (8.242607 - 5.162239 <= 8.0) && (7.989883 - 7.444620 <= 1.0)) }' || {
  print -u2 -- 'error: retained bare-launch startup result exceeds a fixed gate'
  exit 1
}

print -r -- 'PASS: retained bare-launch inputs, historical source digests, summaries, and fixed gates agree'
