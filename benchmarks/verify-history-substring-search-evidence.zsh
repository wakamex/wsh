#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent

local root=${0:A:h:h}
local evidence=$root/benchmarks/history-substring-search-2026-09-03
local temporary=$(mktemp -d /var/tmp/wsh-history-evidence.XXXXXX)
trap 'command rm -rf -- $temporary' EXIT INT TERM

cd $evidence
print -r -- '1da5b0229e0eeabe81de20f5029c71b1e09bdf3999b7053ba843b6c499675b06  baseline.tsv
da5875f141c463f0e877deb4ba97cb268853ab607dc0f8756788f620a0645ff8  candidate.tsv
699fd0dc903cdc16c81933626d48818110b3df0a6fd2605927d6376cc91deb0b  processes.tsv
62ccf0aac381ffdede3f3556b43e6d4c72eec4dc63a54d3caf43b722e118aeb4  summary.tsv' | sha256sum -c - >/dev/null

print -r -- '0b864862a3b48992d7316cc7e585a1315fa389d730c17bf16e2f2bd5918089f3  third_party/zsh-history-substring-search/zsh-history-substring-search.zsh
b2f8ffceca6006eadfdca72a487adb572fe3dccbd5ac3e9f95c50127968454b9  third_party/zsh-history-substring-search/oh-my-zsh-history-substring-search.zsh' | (cd $root && sha256sum -c - >/dev/null)

$root/benchmarks/summarize-history-substring-search.zsh baseline.tsv candidate.tsv $temporary/summary.tsv >/dev/null
diff -u summary.tsv $temporary/summary.tsv

awk -F '\t' '
  NR == 1 { next }
  { samples[$2 SUBSEP $5]++ }
  END {
    expected["baseline" SUBSEP "clean"] = 1
    expected["baseline" SUBSEP "external"] = 1
    expected["candidate" SUBSEP "disabled"] = 1
    expected["candidate" SUBSEP "clean"] = 1
    expected["candidate" SUBSEP "external"] = 1
    for (variant in expected) {
      if (samples[variant] != 40) exit 1
    }
  }
' baseline.tsv candidate.tsv

awk -F '\t' '
  NR == 1 { next }
  $1 == "baseline" && $2 == "external" { baseline_external = $5 }
  $1 == "candidate" && $2 == "disabled" { candidate_disabled = $5 }
  $1 == "candidate" && $2 == "clean" { candidate_clean = $5 }
  $1 == "candidate" && $2 == "external" { candidate_external = $5 }
  END {
    if (candidate_clean - candidate_disabled > 4.0) exit 1
    if (candidate_external - baseline_external > 6.0) exit 1
  }
' summary.tsv

awk -F '\t' '
  NR == 1 { next }
  $2 == "search" { exit 1 }
  $4 == "sha256sum" || $4 == "cmp" { exit 1 }
' processes.tsv

print -r -- 'PASS: history substring search digests, sample counts, startup gates, and process evidence'
