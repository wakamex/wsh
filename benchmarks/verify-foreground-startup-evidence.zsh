#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

readonly root=${0:A:h:h}
readonly evidence=$root/benchmarks/foreground-startup-2026-09-03
readonly metadata=$evidence/metadata.txt
readonly temporary=$(mktemp -d /var/tmp/wsh-foreground-evidence.XXXXXX)
trap 'command rm -rf -- $temporary' EXIT INT TERM

metadata_value() {
  local key=$1
  sed -n "s/^${key}=//p" $metadata
}

verify_hash() {
  local key=$1 file=$2
  local actual=$(sha256sum $file)
  [[ ${actual%% *} == $(metadata_value $key) ]] || {
    print -u2 -- "error: retained foreground-startup hash mismatch: $key"
    exit 1
  }
}

verify_git_object_hash() {
  local key=$1 revision=$2 file_path=$3
  local actual=$(git -C $root show ${revision}:${file_path} | sha256sum)
  [[ ${actual%% *} == $(metadata_value $key) ]] || {
    print -u2 -- "error: retained foreground-startup historical hash mismatch: ${key}"
    exit 1
  }
}

verify_hash latency_sha256 $evidence/latency.tsv
verify_hash latency_summary_sha256 $evidence/latency-summary.tsv
verify_hash ordinary_sha256 $evidence/ordinary.tsv
verify_hash ordinary_summary_sha256 $evidence/ordinary-summary.tsv
verify_hash discarded_explicit_bundle_latency_sha256 $evidence/discarded-explicit-bundle-latency.tsv
verify_hash discarded_explicit_bundle_summary_sha256 $evidence/discarded-explicit-bundle-summary.tsv
verify_hash discarded_polling_unmatched_latency_sha256 $evidence/discarded-polling-unmatched-latency.tsv
verify_hash discarded_polling_unmatched_summary_sha256 $evidence/discarded-polling-unmatched-summary.tsv
verify_hash discarded_blocking_unmatched_latency_sha256 $evidence/discarded-blocking-unmatched-latency.tsv
verify_hash discarded_blocking_unmatched_summary_sha256 $evidence/discarded-blocking-unmatched-summary.tsv
verify_hash discarded_sequential_ordinary_baseline_sha256 $evidence/discarded-sequential-ordinary-baseline.tsv
verify_hash discarded_sequential_ordinary_candidate_sha256 $evidence/discarded-sequential-ordinary-candidate.tsv
verify_hash discarded_sequential_ordinary_summary_sha256 $evidence/discarded-sequential-ordinary-summary.tsv
verify_hash discarded_drift_ordinary_baseline_sha256 $evidence/discarded-drift-ordinary-baseline.tsv
verify_hash discarded_drift_ordinary_candidate_sha256 $evidence/discarded-drift-ordinary-candidate.tsv
verify_hash discarded_drift_ordinary_summary_sha256 $evidence/discarded-drift-ordinary-summary.tsv
verify_hash baseline_correctness_sha256 $evidence/baseline-correctness.log
verify_hash candidate_correctness_sha256 $evidence/candidate-correctness.log
verify_hash wakterm_unit_sha256 $evidence/wakterm-unit.log
verify_hash process_trace_manifest_sha256 $evidence/process-trace/files.sha256
verify_hash discarded_unmatched_process_trace_manifest_sha256 $evidence/discarded-unmatched-process-trace/files.sha256
verify_hash benchmark_sha256 $root/benchmarks/benchmark-foreground-startup.zsh
verify_hash foreground_summarizer_sha256 $root/benchmarks/summarize-foreground-startup.zsh
verify_hash ordinary_benchmark_sha256 $root/benchmarks/benchmark-managed-builds.zsh
verify_hash ordinary_summarizer_sha256 $root/benchmarks/summarize-managed-builds.zsh
verify_hash trace_script_sha256 $root/benchmarks/trace-foreground-startup.zsh
verify_hash plan_sha256 $root/benchmarks/foreground-startup-plan-2026-09-03.md
verify_hash probe_source_sha256 $root/tests/fixtures/foreground-probe.c
verify_hash doctor_source_sha256 $root/crates/wsh/src/doctor.rs
verify_hash zshenv_source_sha256 $root/integration/zdotdir.zshenv
readonly accepted_revision=9037627f6622c5d0b90e873fc67a954c33e0d253
verify_git_object_hash correctness_test_sha256 $accepted_revision tests/foreground-startup.zsh
verify_git_object_hash manager_source_sha256 $accepted_revision crates/wsh/src/main.rs
verify_git_object_hash zshrc_source_sha256 $accepted_revision integration/zdotdir.zshrc
verify_git_object_hash floor_test_sha256 $accepted_revision build/test-development-bundle.zsh

$root/benchmarks/summarize-foreground-startup.zsh $evidence/latency.tsv $temporary/latency-summary.tsv >/dev/null
diff -u $evidence/latency-summary.tsv $temporary/latency-summary.tsv
$root/benchmarks/summarize-managed-builds.zsh $evidence/ordinary.tsv $temporary/ordinary-summary.tsv >/dev/null
diff -u $evidence/ordinary-summary.tsv $temporary/ordinary-summary.tsv

readonly positional_ready_p90=$(awk -F '\t' '$1 == "positional" && $2 == "pty-to-ready" {print $5}' $evidence/latency-summary.tsv)
readonly candidate_ready_p90=$(awk -F '\t' '$1 == "candidate" && $2 == "pty-to-ready" {print $5}' $evidence/latency-summary.tsv)
readonly current_return_p90=$(awk -F '\t' '$1 == "current" && $2 == "ready-to-prompt" {print $5}' $evidence/latency-summary.tsv)
readonly candidate_return_p90=$(awk -F '\t' '$1 == "candidate" && $2 == "ready-to-prompt" {print $5}' $evidence/latency-summary.tsv)
readonly baseline_ordinary_p90=$(awk -F '\t' '$1 == "baseline" {print $4}' $evidence/ordinary-summary.tsv)
readonly candidate_ordinary_p90=$(awk -F '\t' '$1 == "candidate" {print $4}' $evidence/ordinary-summary.tsv)

awk -v baseline=$positional_ready_p90 -v candidate=$candidate_ready_p90 -v maximum=$(metadata_value maximum_ready_p90_regression_ms) 'BEGIN { exit !(candidate - baseline <= maximum) }'
awk -v baseline=$current_return_p90 -v candidate=$candidate_return_p90 -v maximum=$(metadata_value maximum_return_p90_regression_ms) 'BEGIN { exit !(candidate - baseline <= maximum) }'
awk -v baseline=$baseline_ordinary_p90 -v candidate=$candidate_ordinary_p90 -v maximum=$(metadata_value maximum_ordinary_managed_p90_regression_ms) 'BEGIN { exit !(candidate - baseline <= maximum) }'

[[ $(< $evidence/baseline-correctness.log) == 'PASS: current and positional wrappers lose the suspended job as expected' ]]
[[ $(< $evidence/candidate-correctness.log) == 'PASS: structured foreground startup preserves argv, job control, signals, terminal state, startup files, and repeated launch behavior' ]]
grep -F 'test session_persistence::test::restored_harness_runs_as_a_shell_child ... ok' $evidence/wakterm-unit.log >/dev/null

(builtin cd -q $evidence/process-trace && sha256sum -c files.sha256 >/dev/null)
(builtin cd -q $evidence/discarded-unmatched-process-trace && sha256sum -c files.sha256 >/dev/null)
readonly executables=$evidence/process-trace/executables.tsv
[[ $(awk -F '\t' '$1 == "current" && $3 == "zsh" {print $2}' $executables) == 2 ]]
[[ $(awk -F '\t' '$1 == "candidate" && $3 == "zsh" {print $2}' $executables) == 1 ]]
[[ $(awk -F '\t' '$1 == "current" && $3 == "foreground-probe" {print $2}' $executables) == 1 ]]
[[ $(awk -F '\t' '$1 == "candidate" && $3 == "foreground-probe" {print $2}' $executables) == 1 ]]
awk -F '\t' 'NR == 1 {next} $1 == "current" && $3 !~ /^(zsh|wsh-runtime|foreground-probe)$/ {exit 1} $1 == "candidate" && $3 !~ /^(wsh-foreground-candidate-manager|zsh|wsh-runtime|git|foreground-probe)$/ {exit 1}' $executables

print -r -- 'PASS: foreground-startup inputs, summaries, correctness results, process traces, and latency gates agree'
