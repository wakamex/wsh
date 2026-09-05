#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

(( $# == 2 )) || {
  print -u2 -- 'usage: check-profile-gates.zsh PROFILE-SUMMARY RUNTIME-TRACE'
  exit 2
}
(( $+commands[gawk] )) || {
  print -u2 -- 'error: gawk is required'
  exit 2
}

readonly profile_summary=${1:A}
readonly runtime_trace=${2:A}
readonly first_editable_limit_ms=3.000
readonly runtime_ready_limit_ms=3.000
readonly runtime_refresh_limit_ms=0.500

readonly first_result=$(awk -F '\t' '
  NR == 1 {
    if ($0 != "metric\tvariant\tsamples\tmedian_ms\tp90_ms\tmaximum_ms") exit 2
    next
  }
  $1 == "first-editable-overhead" && $2 == "paired" {
    if ($3 != 100) exit 2
    print $5
    found = 1
  }
  END { if (!found) exit 2 }
' $profile_summary)

readonly trace_result=$(gawk -F '\t' '
  NR == 1 {
    expected = "state\titeration\torder\tplain_ready_us\ttraced_ready_us\tready_overhead_us\tplain_refresh_us\ttraced_refresh_us\trefresh_overhead_us"
    if ($0 != expected) exit 2
    next
  }
  {
    if (NF != 9 || ($1 != "clean" && $1 != "dirty" && $1 != "untracked") || $2 !~ /^[0-9]+$/) exit 2
    if ($6 != $5 - $4 || $9 != $8 - $7) exit 2
    key = $1 SUBSEP $2
    if (seen[key]++ || ($2 % 2 && $3 != "plain-first") || (!($2 % 2) && $3 != "traced-first")) exit 2
    ready[++ready_count] = $6 + 0
    refresh[$1, ++state_count[$1]] = $9 + 0
  }
  END {
    if (ready_count != 60 || state_count["clean"] != 20 || state_count["dirty"] != 20 || state_count["untracked"] != 20) exit 2
    asort(ready)
    ready_p90 = ready[54]
    states[1] = "clean"; states[2] = "dirty"; states[3] = "untracked"
    refresh_p90 = -1000000
    for (i = 1; i <= 3; i++) {
      delete values
      for (j = 1; j <= 20; j++) values[j] = refresh[states[i], j]
      asort(values)
      if (values[18] > refresh_p90) refresh_p90 = values[18]
    }
    printf "%.3f\t%.3f\n", ready_p90 / 1000.0, refresh_p90 / 1000.0
  }
' $runtime_trace)
readonly ready_result=${trace_result%%$'\t'*}
readonly refresh_result=${trace_result##*$'\t'}

gate_result() {
  (( $1 <= $2 )) && print pass || print fail
}

print -r -- $'gate\trequired\tobserved\tresult'
printf 'profile-first-editable-p90-overhead-ms\t<=%s\t%.3f\t%s\n' $first_editable_limit_ms $first_result $(gate_result $first_result $first_editable_limit_ms)
printf 'runtime-ready-p90-overhead-ms\t<=%s\t%.3f\t%s\n' $runtime_ready_limit_ms $ready_result $(gate_result $ready_result $runtime_ready_limit_ms)
printf 'runtime-refresh-p90-overhead-ms\t<=%s\t%.3f\t%s\n' $runtime_refresh_limit_ms $refresh_result $(gate_result $refresh_result $runtime_refresh_limit_ms)

(( first_result <= first_editable_limit_ms && ready_result <= runtime_ready_limit_ms && refresh_result <= runtime_refresh_limit_ms ))
