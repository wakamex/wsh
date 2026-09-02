#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

local -F trace_ready_p90_limit_ms=3.000
local -F trace_refresh_p90_limit_ms=0.500
local -i memory_p90_limit_kib=4096
local -i memory_max_limit_kib=5120

if (( $# != 2 )); then
  print -u2 -- 'usage: check-resource-gates.zsh MEMORY.tsv TRACE.tsv'
  return 2
fi
(( $+commands[gawk] )) || {
  print -u2 -- 'error: gawk is required'
  return 2
}

local memory=${1:A}
local trace=${2:A}
[[ -r $memory ]] || { print -u2 -r -- "error: unreadable memory data: $memory"; return 2; }
[[ -r $trace ]] || { print -u2 -r -- "error: unreadable trace data: $trace"; return 2; }

local trace_result
trace_result=$(command gawk -F '\t' '
  NR == 1 {
    expected = "state\titeration\torder\tplain_ready_us\ttraced_ready_us\tready_overhead_us\tplain_refresh_us\ttraced_refresh_us\trefresh_overhead_us"
    if ($0 != expected) {
      print "error: unexpected trace header" > "/dev/stderr"
      exit 2
    }
    next
  }
  {
    if (NF != 9 || ($1 != "clean" && $1 != "dirty" && $1 != "untracked") || $2 !~ /^[0-9]+$/) {
      print "error: malformed trace row " NR > "/dev/stderr"
      exit 2
    }
    if ($4 !~ /^[0-9]+$/ || $5 !~ /^[0-9]+$/ || $6 !~ /^-?[0-9]+$/ || $7 !~ /^[0-9]+$/ || $8 !~ /^[0-9]+$/ || $9 !~ /^-?[0-9]+$/) {
      print "error: malformed trace timing at row " NR > "/dev/stderr"
      exit 2
    }
    key = $1 SUBSEP $2
    if (seen[key]++ || ($2 % 2 && $3 != "plain-first") || (!($2 % 2) && $3 != "traced-first")) {
      print "error: invalid trace iteration or order at row " NR > "/dev/stderr"
      exit 2
    }
    if ($6 != $5 - $4 || $9 != $8 - $7) {
      print "error: inconsistent trace arithmetic at row " NR > "/dev/stderr"
      exit 2
    }
    ready[++ready_count] = $6 + 0
    refresh[$1, ++state_count[$1]] = $9 + 0
  }
  END {
    if (ready_count != 60 || state_count["clean"] != 20 || state_count["dirty"] != 20 || state_count["untracked"] != 20) {
      print "error: trace run must contain 20 pairs for each state" > "/dev/stderr"
      exit 2
    }
    asort(ready)
    ready_p90 = ready[54]
    states[1] = "clean"; states[2] = "dirty"; states[3] = "untracked"
    worst_refresh_p90 = -1000000
    for (i = 1; i <= 3; i++) {
      state = states[i]
      delete values
      for (j = 1; j <= 20; j++) values[j] = refresh[state, j]
      asort(values)
      if (values[18] > worst_refresh_p90) worst_refresh_p90 = values[18]
    }
    printf "%d\t%d\n", ready_p90, worst_refresh_p90
  }
' $trace)
local -F trace_ready_observed=$(( ${trace_result%%$'\t'*} / 1000.0 ))
local -F trace_refresh_observed=$(( ${trace_result##*$'\t'} / 1000.0 ))

local memory_result
memory_result=$(command gawk -F '\t' '
  NR == 1 {
    expected = "iteration\torder\traw_zsh_pss_kib\twsh_zsh_pss_kib\twsh_runtime_pss_kib\twsh_combined_pss_kib\tadded_pss_kib"
    if ($0 != expected) {
      print "error: unexpected memory header" > "/dev/stderr"
      exit 2
    }
    next
  }
  {
    if (NF != 7 || $1 !~ /^[0-9]+$/ || $3 !~ /^[0-9]+$/ || $4 !~ /^[0-9]+$/ || $5 !~ /^[0-9]+$/ || $6 !~ /^[0-9]+$/ || $7 !~ /^-?[0-9]+$/) {
      print "error: malformed memory row " NR > "/dev/stderr"
      exit 2
    }
    if ($1 != NR - 1 || ($1 % 2 && $2 != "raw-first") || (!($1 % 2) && $2 != "wsh-first")) {
      print "error: invalid memory iteration or order at row " NR > "/dev/stderr"
      exit 2
    }
    if ($6 != $4 + $5 || $7 != $6 - $3) {
      print "error: inconsistent memory arithmetic at row " NR > "/dev/stderr"
      exit 2
    }
    values[++count] = $7 + 0
  }
  END {
    if (count != 20) {
      print "error: memory run must contain 20 pairs" > "/dev/stderr"
      exit 2
    }
    asort(values)
    printf "%d\t%d\n", values[18], values[20]
  }
' $memory)
local -i memory_p90_observed=${memory_result%%$'\t'*}
local -i memory_max_observed=${memory_result##*$'\t'}

local -i failed=0
gate_row() {
  local name=$1 required=$2 observed=$3
  local result=pass
  if [[ $4 == 1 ]]; then
    result=fail
    failed=1
  fi
  printf '%s\t%s\t%s\t%s\n' $name $required $observed $result
}

print -r -- $'gate\trequired\tobserved\tresult'
gate_row trace-ready-p90-overhead-ms '<=3.000' $(printf '%.3f' $trace_ready_observed) $(( trace_ready_observed > trace_ready_p90_limit_ms ))
gate_row trace-refresh-p90-overhead-ms '<=0.500' $(printf '%.3f' $trace_refresh_observed) $(( trace_refresh_observed > trace_refresh_p90_limit_ms ))
gate_row retained-added-pss-p90-kib '<=4096' $memory_p90_observed $(( memory_p90_observed > memory_p90_limit_kib ))
gate_row retained-added-pss-max-kib '<=5120' $memory_max_observed $(( memory_max_observed > memory_max_limit_kib ))
(( failed == 0 ))
