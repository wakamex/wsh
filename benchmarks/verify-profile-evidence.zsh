#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent

readonly root=${0:A:h:h}
readonly evidence=$root/benchmarks/profile-2026-09-05
readonly metadata=$evidence/metadata.txt
readonly temporary=$(mktemp -d /var/tmp/wsh-profile-evidence.XXXXXX)
trap 'command rm -rf -- $temporary' EXIT INT TERM

metadata_value() {
  local key=$1
  sed -n "s/^${key}=//p" $metadata
}

verify_hash() {
  local key=$1 file=$2
  local actual=$(sha256sum $file)
  [[ ${actual%% *} == $(metadata_value $key) ]] || {
    print -u2 -- "error: retained profile hash mismatch: ${key}"
    exit 1
  }
}

verify_hash plan_sha256 $root/benchmarks/profile-plan-2026-09-05.md
verify_hash benchmark_sha256 $root/benchmarks/benchmark-profile.zsh
verify_hash summarizer_sha256 $root/benchmarks/summarize-profile.zsh
verify_hash gate_checker_sha256 $root/benchmarks/check-profile-gates.zsh
verify_hash correctness_test_sha256 $root/tests/profile.zsh
verify_hash manager_main_sha256 $root/crates/wsh/src/main.rs
verify_hash manager_library_sha256 $root/crates/wsh/src/lib.rs
verify_hash manager_profile_sha256 $root/crates/wsh/src/profile.rs
verify_hash runtime_sha256 $root/crates/wsh-runtime/src/lib.rs
verify_hash profile_adapter_sha256 $root/integration/profile.zsh
verify_hash integration_adapter_sha256 $root/integration/integration.zsh
verify_hash zshenv_adapter_sha256 $root/integration/zdotdir.zshenv
verify_hash zprofile_adapter_sha256 $root/integration/zdotdir.zprofile
verify_hash zshrc_adapter_sha256 $root/integration/zdotdir.zshrc
verify_hash zlogin_adapter_sha256 $root/integration/zdotdir.zlogin
verify_hash bundle_builder_sha256 $root/build/build-development-bundle.zsh
verify_hash bundle_test_runner_sha256 $root/build/test-development-bundle.zsh
verify_hash samples_sha256 $evidence/samples.tsv
verify_hash summary_sha256 $evidence/summary.tsv
verify_hash paired_overhead_sha256 $evidence/paired-overhead.tsv
verify_hash functions_samples_sha256 $evidence/functions-samples.tsv
verify_hash functions_summary_sha256 $evidence/functions-summary.tsv
verify_hash runtime_trace_sha256 $evidence/runtime-trace.tsv
verify_hash gates_sha256 $evidence/gates.tsv
verify_hash correctness_log_sha256 $evidence/correctness.log

$root/benchmarks/summarize-profile.zsh $evidence/samples.tsv $temporary/summary.tsv >/dev/null
$root/benchmarks/summarize-profile.zsh $evidence/functions-samples.tsv $temporary/functions-summary.tsv >/dev/null
$root/benchmarks/check-profile-gates.zsh $temporary/summary.tsv $evidence/runtime-trace.tsv > $temporary/gates.tsv
diff -u $evidence/summary.tsv $temporary/summary.tsv
diff -u $evidence/functions-summary.tsv $temporary/functions-summary.tsv
diff -u $evidence/gates.tsv $temporary/gates.tsv

[[ $(awk -F '\t' 'NR > 1 { count++ } END { print count + 0 }' $evidence/samples.tsv) == 200 ]]
[[ $(awk -F '\t' 'NR > 1 { count++ } END { print count + 0 }' $evidence/functions-samples.tsv) == 80 ]]
[[ $(awk -F '\t' 'NR > 1 { count++ } END { print count + 0 }' $evidence/runtime-trace.tsv) == 60 ]]
[[ $(awk -F '\t' 'NR > 1 && $4 == "normal" { count++ } END { print count + 0 }' $evidence/samples.tsv) == 100 ]]
[[ $(awk -F '\t' 'NR > 1 && $4 == "profile" { count++ } END { print count + 0 }' $evidence/samples.tsv) == 100 ]]
[[ $(awk -F '\t' 'NR > 1 && $4 == "normal" { count++ } END { print count + 0 }' $evidence/functions-samples.tsv) == 40 ]]
[[ $(awk -F '\t' 'NR > 1 && $4 == "profile" { count++ } END { print count + 0 }' $evidence/functions-samples.tsv) == 40 ]]
[[ $(awk -F '\t' 'NR > 1 && $4 != "pass" { count++ } END { print count + 0 }' $evidence/gates.tsv) == 0 ]]

print -r -- 'PASS: retained profile inputs, summaries, sample counts, and fixed overhead gates agree'
