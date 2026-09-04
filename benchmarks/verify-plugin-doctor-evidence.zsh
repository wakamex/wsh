#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

readonly root=${0:A:h:h}
readonly evidence=$root/benchmarks/plugin-doctor-2026-09-03
readonly metadata=$evidence/metadata.txt
readonly temporary=$(mktemp -d /var/tmp/wsh-plugin-doctor-evidence.XXXXXX)
trap 'command rm -rf -- $temporary' EXIT INT TERM

metadata_value() {
  local key=$1
  sed -n "s/^${key}=//p" $metadata
}

verify_hash() {
  local key=$1 file=$2
  local actual=$(sha256sum $file)
  [[ ${actual%% *} == $(metadata_value $key) ]] || {
    print -u2 -- "error: retained plugin-doctor hash mismatch: $key"
    exit 1
  }
}

verify_git_object_hash() {
  local key=$1 revision=$2 file_path=$3
  local actual=$(git -C $root show ${revision}:${file_path} | sha256sum)
  [[ ${actual%% *} == $(metadata_value $key) ]] || {
    print -u2 -- "error: retained plugin-doctor historical hash mismatch: ${key}"
    exit 1
  }
}

verify_hash startup_baseline_sha256 $evidence/startup-baseline.tsv
verify_hash startup_candidate_sha256 $evidence/startup-candidate.tsv
verify_hash startup_summary_sha256 $evidence/startup-summary.tsv
verify_hash discarded_host_config_baseline_sha256 $evidence/discarded-host-config-baseline.tsv
verify_hash discarded_host_config_candidate_sha256 $evidence/discarded-host-config-candidate.tsv
verify_hash correctness_log_sha256 $evidence/correctness.log
verify_hash doctor_source_sha256 $root/crates/wsh/src/doctor.rs
verify_hash doctor_test_sha256 $root/tests/plugin-doctor.zsh
verify_hash benchmark_sha256 $root/benchmarks/benchmark-first-editable.zsh
verify_hash summarizer_sha256 $root/benchmarks/summarize-plugin-doctor.zsh
verify_hash plan_sha256 $root/benchmarks/plugin-doctor-plan-2026-09-03.md
readonly previous_accepted_revision=9037627f6622c5d0b90e873fc67a954c33e0d253
verify_git_object_hash manager_source_sha256 $previous_accepted_revision crates/wsh/src/main.rs
verify_git_object_hash floor_test_sha256 $previous_accepted_revision build/test-development-bundle.zsh

$root/benchmarks/summarize-plugin-doctor.zsh $evidence/startup-baseline.tsv $evidence/startup-candidate.tsv $temporary/summary.tsv >/dev/null
diff -u $evidence/startup-summary.tsv $temporary/summary.tsv

readonly baseline_p90=$(awk -F '\t' '$1 == "baseline" && $2 == "managed-complete" {print $5}' $evidence/startup-summary.tsv)
readonly candidate_p90=$(awk -F '\t' '$1 == "candidate" && $2 == "managed-complete" {print $5}' $evidence/startup-summary.tsv)
readonly maximum_regression=$(metadata_value maximum_managed_p90_regression_ms)
awk -v baseline=$baseline_p90 -v candidate=$candidate_p90 -v maximum=$maximum_regression 'BEGIN { exit !(candidate - baseline <= maximum) }' || {
  print -u2 -- 'error: retained plugin-doctor startup result exceeds its fixed gate'
  exit 1
}

[[ $(grep -c '^PASS:' $evidence/correctness.log) == 5 ]]
[[ $(metadata_value startup_user_configuration) == isolated-empty-zshrc ]]
[[ $(metadata_value startup_samples_per_variant) == 40 ]]

print -r -- 'PASS: plugin-doctor inputs, summaries, correctness results, and startup gate agree'
