#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly repository_root=${0:A:h:h}
readonly evidence=${repository_root}/benchmarks/update-cli-2026-09-03
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
    print -u2 -- "error: retained update CLI evidence hash mismatch: $key"
    exit 1
  }
}

verify_git_object_hash() {
  local key=$1
  local revision=$2
  local input_path=$3
  local actual=$(git show ${revision}:${input_path} | sha256sum)
  [[ ${actual%% *} == $(metadata_value $key) ]] || {
    print -u2 -- "error: retained update CLI source hash mismatch: $key"
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
verify_git_object_hash update_module_sha256 $source_revision crates/wsh/src/update.rs
verify_git_object_hash update_test_sha256 $source_revision tests/update-cli.zsh
verify_git_object_hash validation_workflow_sha256 $source_revision .github/workflows/validation.yml
verify_git_object_hash benchmark_sha256 $source_revision benchmarks/benchmark-first-editable.zsh
verify_git_object_hash plan_sha256 $source_revision benchmarks/update-cli-plan-2026-09-03.md

readonly raw=$(summarize_variant raw)
readonly direct=$(summarize_variant direct-complete)
readonly managed=$(summarize_variant managed-complete)
[[ $raw == $'40\t4.930257\t5.087376\t5.172968' ]] || {
  print -u2 -- "error: retained raw startup summary changed: $raw"
  exit 1
}
[[ $direct == $'40\t7.197857\t7.392883\t7.766008' ]] || {
  print -u2 -- "error: retained direct startup summary changed: $direct"
  exit 1
}
[[ $managed == $'40\t7.810354\t8.015871\t8.318186' ]] || {
  print -u2 -- "error: retained managed startup summary changed: $managed"
  exit 1
}

awk 'BEGIN { exit !((8.015871 - 5.087376 <= 5.0) && (8.318186 - 5.172968 <= 8.0) && (8.015871 - 7.392883 <= 1.0)) }' || {
  print -u2 -- 'error: retained update CLI startup result exceeds a fixed gate'
  exit 1
}

print -r -- 'PASS: retained update CLI inputs, historical source digests, summaries, and fixed gates agree'
