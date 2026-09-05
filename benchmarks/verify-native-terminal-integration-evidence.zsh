#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent

readonly root=${0:A:h:h}
readonly evidence=$root/benchmarks/native-terminal-integration-2026-09-04
readonly metadata=$evidence/metadata.txt
readonly temporary=$(mktemp -d /var/tmp/wsh-native-terminal-evidence.XXXXXX)
readonly accepted_revision=7fefaa6b7083c3fd174536b240a2dc94005a79d3
trap 'command rm -rf -- $temporary' EXIT INT TERM

metadata_value() {
  local key=$1
  sed -n "s/^${key}=//p" $metadata
}

verify_hash() {
  local key=$1 file=$2
  local actual=$(sha256sum $file)
  [[ ${actual%% *} == $(metadata_value $key) ]] || {
    print -u2 -- "error: retained native-terminal hash mismatch: ${key}"
    exit 1
  }
}

verify_git_object_hash() {
  local key=$1 revision=$2 file=$3
  local actual=$(git -C $root show ${revision}:${file} | sha256sum)
  [[ ${actual%% *} == $(metadata_value $key) ]] || {
    print -u2 -- "error: retained native-terminal Git object hash mismatch: ${key}"
    exit 1
  }
}

verify_hash baseline_native_counts_sha256 $evidence/baseline-native-counts.tsv
verify_hash baseline_duplicate_counts_sha256 $evidence/baseline-duplicate-counts.tsv
verify_hash baseline_coexist_counts_sha256 $evidence/baseline-coexist-counts.tsv
verify_hash candidate_native_counts_sha256 $evidence/candidate-native-counts.tsv
verify_hash candidate_coexist_counts_sha256 $evidence/candidate-coexist-counts.tsv
verify_hash baseline_native_transcript_sha256 $evidence/baseline-native.bin
verify_hash baseline_duplicate_transcript_sha256 $evidence/baseline-duplicate.bin
verify_hash baseline_coexist_transcript_sha256 $evidence/baseline-coexist.bin
verify_hash candidate_native_transcript_sha256 $evidence/candidate-native.bin
verify_hash candidate_coexist_transcript_sha256 $evidence/candidate-coexist.bin
verify_hash foreground_baseline_transcript_sha256 $evidence/foreground-baseline.bin
verify_hash foreground_candidate_transcript_sha256 $evidence/foreground-candidate.bin
verify_hash prompt_cycle_sha256 $evidence/prompt-cycle.tsv
verify_hash prompt_cycle_summary_sha256 $evidence/prompt-cycle-summary.tsv
verify_hash process_trace_manifest_sha256 $evidence/process-trace/files.sha256
verify_hash benchmark_script_sha256 $root/benchmarks/benchmark-native-terminal-integration.zsh
verify_hash summarizer_script_sha256 $root/benchmarks/summarize-native-terminal-integration.zsh
verify_hash trace_script_sha256 $root/benchmarks/trace-native-terminal-integration.zsh
verify_hash plan_sha256 $root/benchmarks/native-terminal-integration-plan-2026-09-04.md
verify_hash correctness_test_sha256 $root/tests/native-terminal-integration.zsh
verify_hash foreground_test_sha256 $root/tests/foreground-startup.zsh
verify_hash zsh_source_patch_sha256 $root/build/zsh-patches/cad0d67c-terminal-integration.patch
verify_git_object_hash manager_source_sha256 $accepted_revision crates/wsh/src/main.rs
verify_hash zshrc_source_sha256 $root/integration/zdotdir.zshrc
verify_hash build_zsh_source_sha256 $root/build/build-zsh.zsh
verify_hash build_bundle_source_sha256 $root/build/build-development-bundle.zsh
verify_git_object_hash zsh_source_lock_sha256 $accepted_revision build/zsh-sources/zsh-cad0d67c.json
verify_git_object_hash floor_test_source_sha256 $accepted_revision build/test-development-bundle.zsh

[[ $(git -C $root show ${accepted_revision}:build/zsh-sources/zsh-cad0d67c.json | jq -r '.source_patches[0].sha256') == $(metadata_value zsh_source_patch_sha256) ]]

$root/benchmarks/summarize-native-terminal-integration.zsh $evidence/prompt-cycle.tsv $temporary/summary.tsv >/dev/null
diff -u $evidence/prompt-cycle-summary.tsv $temporary/summary.tsv

for variant in native duplicate coexist; do
  [[ $(awk -F '\t' -v variant=$variant 'NR > 1 && $1 == variant { count++ } END { print count + 0 }' $evidence/prompt-cycle.tsv) == 45 ]]
  [[ $(awk -F '\t' -v variant=$variant '$1 == variant && $2 > 5 { count++ } END { print count + 0 }' $evidence/prompt-cycle.tsv) == 40 ]]
done

native_p90=$(awk -F '\t' '$1 == "native" { print $4 }' $evidence/prompt-cycle-summary.tsv)
coexist_p90=$(awk -F '\t' '$1 == "coexist" { print $4 }' $evidence/prompt-cycle-summary.tsv)
awk -v native=$native_p90 -v coexist=$coexist_p90 -v maximum=$(metadata_value maximum_coexist_p90_regression_ms) 'BEGIN { exit !(coexist - native <= maximum) }'

[[ $(tail -n 1 $evidence/baseline-native-counts.tsv) == $'native\t10\t0\t10\t7\t6\t2\t1\t0\t9\t7' ]]
[[ $(tail -n 1 $evidence/baseline-duplicate-counts.tsv) == $'duplicate\t19\t0\t20\t14\t14\t11\t10\t1\t9\t7' ]]
[[ $(tail -n 1 $evidence/baseline-coexist-counts.tsv) == $'coexist\t10\t0\t10\t7\t6\t2\t1\t0\t9\t7' ]]
[[ $(tail -n 1 $evidence/candidate-native-counts.tsv) == $'native\t10\t10\t10\t7\t6\t11\t10\t1\t9\t7' ]]
[[ $(tail -n 1 $evidence/candidate-coexist-counts.tsv) == $'coexist\t10\t10\t10\t7\t6\t11\t10\t1\t9\t7' ]]

(builtin cd -q $evidence/process-trace && sha256sum -c files.sha256 >/dev/null)
[[ $(awk -F '\t' '$1 == "native" { print $3 }' $evidence/process-trace/process-summary.tsv) == 0 ]]
[[ $(awk -F '\t' '$1 == "duplicate" { print $3 }' $evidence/process-trace/process-summary.tsv) == 9 ]]
[[ $(awk -F '\t' '$1 == "coexist" { print $3 }' $evidence/process-trace/process-summary.tsv) == 0 ]]

baseline_foreground=$(< $evidence/foreground-baseline.bin)
candidate_foreground=$(< $evidence/foreground-candidate.bin)
[[ $baseline_foreground != *$'\e]133;C\e\\'* && $baseline_foreground != *$'\e]133;D\e\\'* ]]
[[ $candidate_foreground == *$'\e]133;C\e\\'*$'WSH_FOREGROUND_READY\t'*$'\e]133;D\e\\'*$'\e]7;file:'*$'\e]133;A;cl=m;aid=z'*$'\e]133;B\e\\'* ]]

print -r -- 'PASS: native terminal inputs, summaries, transcripts, process traces, and latency gates agree'
