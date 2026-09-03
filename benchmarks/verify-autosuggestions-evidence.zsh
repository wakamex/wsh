#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent

local root=${0:A:h:h}
local evidence=$root/benchmarks/autosuggestions-2026-09-03
local temporary=$(mktemp -d /var/tmp/wsh-autosuggestions-evidence.XXXXXX)
trap 'command rm -rf -- $temporary' EXIT INT TERM

cd $evidence
print -r -- '4758eae3a9f17077f1e8a6ea2b6867b1f79865a6dad10e8aa9aacff86215d6ac  startup-baseline.tsv
f78d1c7512f57e02b624c604d9d6f8bc008734e8971c8dc6e041fa17eeb1f7d3  startup-candidate.tsv
ea9ed8c959524f0540cfc2d7ece42fe6ddfcc32e3da1bbdb94915cf732cc1d08  prompt-baseline.tsv
23c9959d1448ac8e918cb38f65f0ffcacd0550eb462a324aec9db5be6a549e0a  prompt-candidate.tsv
ae54cc9befcbd80b9004074fe84369e8ff2e6f69d090c0272a9e8da453c25303  edit-baseline.tsv
991456d140965b849603e260618ef08af0027d3ad4c9aed51ee2702a5360861d  edit-candidate.tsv
687b4c489732ae5661b7b8960eb351ad843db2c46bb025183761e2c188641441  summary.tsv
ae66a30541e4f15aefc9b12e188eb071d0080ee84ed7ec66f50e5c32320fbf38  process-trace/edit-window.trace
ebafdc07e6614d28d5138860689c950cb69cf15cded7be9fff42a852e07d9b97  process-trace/executables.tsv
3d2b979dde0173fa55947604c14cf5812b43ab68d8128d29b19af96037bd84aa  process-trace/metadata.txt' | sha256sum -c - >/dev/null

print -r -- 'eec7ba8f7a71414ace0ea0fab0908d005b24cf65d83b169c0ff97815d3cfc51a  third_party/zsh-autosuggestions/zsh-autosuggestions.zsh
2d369f247f2a7278c83e90ba48690d0a1f63528837d034055b1cbec87d86a6d6  integration/autosuggestions.zsh
add0274292b3ef623e24a169ca1c53a7dcd4778b0ec034c3c7fb430006af888e  integration/zdotdir.zshrc' | (cd $root && sha256sum -c - >/dev/null)

$root/benchmarks/summarize-autosuggestions.zsh startup-baseline.tsv startup-candidate.tsv prompt-baseline.tsv prompt-candidate.tsv edit-baseline.tsv edit-candidate.tsv $temporary/summary.tsv >/dev/null
diff -u summary.tsv $temporary/summary.tsv

awk -F '\t' '
  FNR == 1 { next }
  { samples[$2 SUBSEP $5]++ }
  END {
    expected["baseline" SUBSEP "clean"] = 40
    expected["baseline" SUBSEP "external"] = 40
    expected["baseline" SUBSEP "external-manual"] = 40
    expected["candidate" SUBSEP "disabled"] = 40
    expected["candidate" SUBSEP "clean"] = 40
    expected["candidate" SUBSEP "external"] = 40
    for (variant in expected) {
      if (samples[variant] != expected[variant]) exit 1
    }
  }
' startup-baseline.tsv startup-candidate.tsv

awk -F '\t' '
  FNR == 1 { next }
  { samples[$2 SUBSEP $5]++ }
  END {
    expected["baseline" SUBSEP "clean"] = 200
    expected["baseline" SUBSEP "external"] = 200
    expected["baseline" SUBSEP "external-manual"] = 200
    expected["candidate" SUBSEP "disabled"] = 200
    expected["candidate" SUBSEP "clean"] = 200
    expected["candidate" SUBSEP "external"] = 200
    for (variant in expected) {
      if (samples[variant] != expected[variant]) exit 1
    }
  }
' prompt-baseline.tsv prompt-candidate.tsv

awk -F '\t' '
  FNR == 1 { next }
  { samples[$2 SUBSEP $5]++ }
  END {
    expected["baseline" SUBSEP "external-manual"] = 100
    expected["candidate" SUBSEP "clean"] = 100
    expected["candidate" SUBSEP "external"] = 100
    for (variant in expected) {
      if (samples[variant] != expected[variant]) exit 1
    }
  }
' edit-baseline.tsv edit-candidate.tsv

awk -F '\t' '
  NR == 1 { next }
  $1 == "first-editable" && $2 == "baseline" && $3 == "clean" { startup_baseline_clean = $6 }
  $1 == "first-editable" && $2 == "baseline" && $3 == "external" { startup_baseline_external = $6 }
  $1 == "first-editable" && $2 == "candidate" && $3 == "disabled" { startup_candidate_disabled = $6 }
  $1 == "first-editable" && $2 == "candidate" && $3 == "clean" { startup_candidate_clean = $6 }
  $1 == "first-editable" && $2 == "candidate" && $3 == "external" { startup_candidate_external = $6 }
  $1 == "settled-prompt" && $2 == "baseline" && $3 == "external" { prompt_baseline_external = $6 }
  $1 == "settled-prompt" && $2 == "candidate" && $3 == "clean" { prompt_candidate_clean = $6 }
  $1 == "suggestion-available" && $2 == "baseline" && $3 == "external-manual" { available_baseline = $6 }
  $1 == "suggestion-available" && $2 == "candidate" && $3 == "clean" { available_clean = $6 }
  $1 == "suggestion-available" && $2 == "candidate" && $3 == "external" { available_external = $6 }
  $1 == "suggestion-accepted" && $2 == "baseline" && $3 == "external-manual" { accepted_baseline = $6 }
  $1 == "suggestion-accepted" && $2 == "candidate" && $3 == "clean" { accepted_clean = $6 }
  $1 == "suggestion-accepted" && $2 == "candidate" && $3 == "external" { accepted_external = $6 }
  END {
    if (startup_candidate_clean - startup_baseline_external > 1.0) exit 1
    if (startup_candidate_external - startup_baseline_external > 4.0) exit 1
    if (startup_candidate_disabled - startup_baseline_clean > 0.25) exit 1
    if (prompt_candidate_clean > prompt_baseline_external * 0.80) exit 1
    if (available_clean > available_baseline * 1.20 || available_external > available_baseline * 1.20) exit 1
    if (accepted_clean > accepted_baseline * 1.20 || accepted_external > accepted_baseline * 1.20) exit 1
  }
' summary.tsv

[[ $(sed -n 's/^owner=//p' process-trace/metadata.txt) == 'wsh|1' ]]
[[ $(sed -n 's/^edit_window_process_creations=//p' process-trace/metadata.txt) == 1 ]]
[[ $(sed -n 's/^edit_window_execve=//p' process-trace/metadata.txt) == 0 ]]
awk -F '\t' 'NR > 1 && ($2 == "sha256sum" || $2 == "cmp") { exit 1 }' process-trace/executables.tsv
awk '/ execve\(/ { exit 1 }' process-trace/edit-window.trace

print -r -- 'PASS: autosuggestions digests, sample counts, startup, prompt, editing, and process gates'
