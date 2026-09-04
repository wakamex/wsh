#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

readonly root=${0:A:h:h}
readonly evidence=$root/benchmarks/edge-zsh-2026-09-03
readonly metadata=$evidence/metadata.txt
[[ -d $evidence && -f $metadata ]] || {
  print -u2 -- 'error: edge-Zsh evidence is missing'
  exit 1
}

metadata_value() {
  local key=$1
  sed -n "s/^${key}=//p" $metadata
}

verify_sha256() {
  local expected=$1 file=$2 actual
  actual=$(sha256sum $file)
  actual=${actual%% *}
  [[ $actual == $expected ]] || {
    print -u2 -- "digest mismatch for ${file#$root/}: expected $expected, got $actual"
    return 1
  }
}

verify_sha256 $(metadata_value stable_source_lock_sha256) $root/build/zsh-sources/zsh-5.9.2.json
verify_sha256 $(metadata_value edge_source_lock_sha256) $root/build/zsh-sources/zsh-cad0d67c.json
verify_sha256 $(metadata_value edge_test_patch_sha256) $root/build/zsh-test-patches/cad0d67c-prompt-fixture.patch
verify_sha256 $(metadata_value summary_sha256) $evidence/summary.tsv

grep -Fqx '63 successful test scripts, 0 failures, 2 skipped' $evidence/zsh-upstream-stable.log
grep -Fqx '75 successful test scripts, 0 failures, 2 skipped' $evidence/zsh-upstream-edge.log
grep -Fqx 'PASS: current-shell command substitution, named references, named layered highlighting, and exact executable path' $evidence/edge-features.log
grep -Fqx 'PASS: history substring search candidate behavior' $evidence/history-correctness-stable.log
grep -Fqx 'PASS: history substring search candidate behavior' $evidence/history-correctness-edge.log
grep -Fqx 'PASS: autosuggestion display, acceptance, ownership, configuration, composition, custom widgets, and cancellation' $evidence/autosuggestions-correctness-stable.log
grep -Fqx 'PASS: autosuggestion display, acceptance, ownership, configuration, composition, custom widgets, and cancellation' $evidence/autosuggestions-correctness-edge.log
grep -Fqx 'PASS: syntax highlighting ownership, semantics, configuration, hooks, and editing-default composition' $evidence/syntax-correctness-stable.log
grep -Fqx 'PASS: syntax highlighting ownership, semantics, configuration, hooks, and editing-default composition' $evidence/syntax-correctness-edge.log

for directory in \
  minimal-final-stable-forward minimal-final-stable-reverse \
  minimal-final-edge-forward minimal-final-edge-reverse \
  wakamex-final-stable-forward wakamex-final-stable-reverse \
  wakamex-final-edge-forward wakamex-final-edge-reverse; do
  run=$evidence/$directory
  [[ $(sed -n 's/^accepted=//p' $run/metadata.txt) == 1 ]]
  for artifact in summary samples telemetry; do
    expected=$(sed -n "s/^${artifact}_sha256=//p" $run/metadata.txt)
    verify_sha256 $expected $run/$artifact.tsv
  done
  awk -F '\t' '
    NR == 1 { next }
    $3 == "raw" { next }
    NF != 36 || $15 != 1 || $16 != 0 ||
      $19 != 1 || $20 != 1 || $21 != 0 || $22 != 20 ||
      $25 != 1 || $26 != 1 || $27 != 0 || $28 != 20 ||
      $31 != 1 || $32 != 1 || $33 != 0 || $34 != 20 ||
      $35 != 1 || $36 != 1 { exit 1 }
  ' $run/summary.tsv
done

readonly temporary=$(mktemp -d /tmp/wsh-edge-summary.XXXXXX)
trap 'command rm -rf -- $temporary' EXIT INT TERM
$root/benchmarks/summarize-edge-zsh.zsh $evidence $temporary/summary.tsv >/dev/null
diff -u $evidence/summary.tsv $temporary/summary.tsv

awk -F '\t' '
  NR == 1 { next }
  {
    key = $1 SUBSEP $2 SUBSEP $3 SUBSEP $4
    p90[key] = $7 + 0
    maximum[key] = $8 + 0
  }
  END {
    if (p90["first-editable" SUBSEP "edge" SUBSEP "raw" SUBSEP "initial"] - p90["first-editable" SUBSEP "stable" SUBSEP "raw" SUBSEP "initial"] > 1.0) exit 1
    if (p90["first-editable" SUBSEP "edge" SUBSEP "direct" SUBSEP "initial"] - p90["first-editable" SUBSEP "stable" SUBSEP "direct" SUBSEP "initial"] > 1.0) exit 1
    if (p90["first-editable" SUBSEP "edge" SUBSEP "managed" SUBSEP "initial"] - p90["first-editable" SUBSEP "stable" SUBSEP "managed" SUBSEP "initial"] > 1.0) exit 1
    split("disabled history autosuggestions syntax all", defaults, " ")
    for (i in defaults) {
      configuration = defaults[i]
      if (p90["interactive-default-startup" SUBSEP "edge" SUBSEP configuration SUBSEP "initial"] - p90["interactive-default-startup" SUBSEP "stable" SUBSEP configuration SUBSEP "initial"] > 1.0) exit 1
    }
    split("short long", redraws, " ")
    for (i in redraws) {
      workload = redraws[i]
      if (p90["syntax-highlight-redraw" SUBSEP "edge" SUBSEP "bundled" SUBSEP workload] > 1.2 * p90["syntax-highlight-redraw" SUBSEP "stable" SUBSEP "bundled" SUBSEP workload]) exit 1
    }
    if (p90["retained-memory" SUBSEP "edge" SUBSEP "wsh-added" SUBSEP "settled"] > 4096) exit 1
    if (maximum["retained-memory" SUBSEP "edge" SUBSEP "wsh-added" SUBSEP "settled"] > 5120) exit 1
    split("minimal wakamex", renderers, " ")
    split("clean dirty untracked", states, " ")
    for (r in renderers) for (s in states) {
      renderer = renderers[r]; state = states[s]
      wsh = renderer "-wsh"; raw = renderer "-raw"
      if (maximum["git-prompt-first" SUBSEP "edge" SUBSEP wsh SUBSEP state] - maximum["git-prompt-first" SUBSEP "edge" SUBSEP raw SUBSEP state] > 2.0) exit 1
      if (p90["git-prompt-settled" SUBSEP "edge" SUBSEP wsh SUBSEP state] - p90["git-prompt-settled" SUBSEP "edge" SUBSEP raw SUBSEP state] > 7.1) exit 1
      if (maximum["git-prompt-settled" SUBSEP "edge" SUBSEP wsh SUBSEP state] - maximum["git-prompt-settled" SUBSEP "edge" SUBSEP raw SUBSEP state] > 8.0) exit 1
    }
  }
' $evidence/summary.tsv

trap - EXIT INT TERM
command rm -rf -- $temporary
print -r -- 'PASS: pinned edge Zsh evidence and fixed gates'
