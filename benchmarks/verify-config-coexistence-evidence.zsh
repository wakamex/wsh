#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

local root=${0:A:h:h}
local evidence=$root/benchmarks/zsh-config-coexistence-2026-09-03
local temporary=$(mktemp -d /var/tmp/wsh-config-evidence.XXXXXX)
trap 'command rm -rf -- $temporary' EXIT INT TERM

cd $evidence
print -r -- 'e5624c344329566c7b4839e992687426cfefc1dc2ab5cbbc1d0079d0e2283db1  baseline.txt
b153ed0fe39fe65fb0e8d83572855cf3ccabb83d9cb514055d209904f2919ff6  ownership.tsv
224846f08c21c003200f836d0f8cc17e4776d2874b2398050926cb8035910b43  startup.tsv
f713e45b3704b3eca7d33b6197bb0000a469d3e96b8c4b94b16ed9c234added3  startup-summary.tsv
20a543ccda9453c6d1515f012f62dff9fc1a97d483b4113312a22327848db25f  startup-processes.tsv' | sha256sum -c - >/dev/null

$root/benchmarks/summarize-config-startup.zsh startup.tsv $temporary/startup-summary.tsv >/dev/null
diff -u startup-summary.tsv $temporary/startup-summary.tsv

awk -F '\t' '
  NR == 1 { next }
  { samples[$4]++ }
  END {
    expected["plain-direct"] = expected["empty"] = expected["plain"] = 1
    expected["omz-none"] = expected["robbyrussell"] = expected["agnoster"] = 1
    expected["wakamex"] = expected["plugins"] = expected["wakamex-plugins"] = 1
    for (variant in expected) {
      if (samples[variant] != 40) exit 1
    }
  }
' startup.tsv

[[ $(<baseline.txt) == 'PASS: user startup configuration missing under managed wsh' ]]

awk -F '\t' '
  NR == 1 { next }
  $1 == "plain-direct" { direct = $4 }
  $1 == "plain" { managed = $4 }
  END { if (managed - direct > 1.0) exit 1 }
' startup-summary.tsv

awk -F '\t' '
  BEGIN {
    expected_git["omz-none"] = 1
    expected_git["robbyrussell"] = 6
    expected_git["agnoster"] = 1
    expected_git["wakamex"] = 2
    expected_git["plugins"] = 1
    expected_git["wakamex-plugins"] = 2
  }
  NR == 1 { next }
  {
    seen[$1]++
    if ($2 != "loaded" || $3 != "loaded" || $4 != "ready" || $5 != "wsh") exit 1
    if ($10 != expected_git[$1]) exit 1
    if ($11 !~ /(^|,)_wsh_runtime_precmd(,|$)/) exit 1
    if ($12 !~ /(^|,)_wsh_runtime_preexec(,|$)/) exit 1
    if ($13 !~ /(^|,)_wsh_runtime_stop(,|$)/) exit 1
    if (($1 == "plugins" || $1 == "wakamex-plugins") && ($6 != 1 || $7 != 1 || $8 != 1)) exit 1
  }
  END {
    for (variant in expected_git) {
      if (seen[variant] != 1) exit 1
    }
  }
' ownership.tsv

diff -u <(print -r -- $'variant\tcount\texecutable\ndirect\t1\twsh-runtime\ndirect\t1\tzsh\ndirect\t1\tgit\nmanaged\t1\twsh-runtime\nmanaged\t1\tzsh\nmanaged\t1\twsh\nmanaged\t1\tgit') startup-processes.tsv

print -r -- 'PASS: configuration coexistence sample counts, summary, startup gate, ownership, plugins, and Git-process evidence'
