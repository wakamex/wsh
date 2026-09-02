#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

local -F trace_first_p90_limit_ms=0.500
local -F trace_settled_p90_limit_ms=0.500
local -i memory_p90_limit_kib=4096
local -i memory_max_limit_kib=5120

if (( $# != 3 )); then
  print -u2 -- 'usage: check-resource-gates.zsh MEMORY.tsv TRACE_FORWARD_DIR TRACE_REVERSE_DIR'
  return 2
fi
(( $+commands[gawk] )) || {
  print -u2 -- 'error: gawk is required'
  return 2
}

local memory=${1:A}
local forward=${2:A}
local reverse=${3:A}
[[ -r $memory ]] || { print -u2 -r -- "error: unreadable memory data: $memory"; return 2; }

trace_block() {
  local directory=$1 expected_targets=$2
  local metadata=$directory/metadata.txt distribution=$directory/distribution.tsv summary=$directory/summary.tsv
  [[ -r $metadata && -r $distribution && -r $summary ]] || {
    print -u2 -r -- "error: incomplete trace run: $directory"
    return 2
  }
  [[ $(sed -n 's/^accepted=//p' $metadata) == 1 ]] || {
    print -u2 -r -- "error: unaccepted trace run: $directory"
    return 2
  }
  [[ $(sed -n 's/^iterations=//p' $metadata) == 20 ]] || {
    print -u2 -r -- "error: trace run must use 20 iterations: $directory"
    return 2
  }
  [[ $(sed -n 's/^targets=//p' $metadata) == $expected_targets ]] || {
    print -u2 -r -- "error: unexpected target order in $directory"
    return 2
  }

  command gawk -F '\t' '
    NR == 1 {
      if (NF != 15 || $1 != "target" || $2 != "state" || $6 != "first_p90_ms" || $10 != "settled_p90_ms") {
        print "error: unexpected distribution header" > "/dev/stderr"
        exit 2
      }
      next
    }
    $1 == "wsh" || $1 == "wsh-trace" {
      if ($2 != "clean" && $2 != "dirty" && $2 != "untracked") {
        print "error: unexpected trace state" > "/dev/stderr"
        exit 2
      }
      if ($3 != 20 || $12 != "1.000" || $13 != "1.000" || $14 != "0.000" || $15 != "20/20") {
        print "error: trace correctness or process invariant failed" > "/dev/stderr"
        exit 1
      }
      key = $1 SUBSEP $2
      if (seen[key]++) {
        print "error: duplicate trace row" > "/dev/stderr"
        exit 2
      }
      first[key] = $6 + 0
      settled[key] = $10 + 0
    }
    END {
      states[1] = "clean"; states[2] = "dirty"; states[3] = "untracked"
      worst_first = -1000000
      worst_settled = -1000000
      for (i = 1; i <= 3; i++) {
        state = states[i]
        plain = "wsh" SUBSEP state
        traced = "wsh-trace" SUBSEP state
        if (!(plain in seen) || !(traced in seen)) {
          print "error: missing trace row" > "/dev/stderr"
          exit 2
        }
        first_delta = first[traced] - first[plain]
        settled_delta = settled[traced] - settled[plain]
        if (first_delta > worst_first) worst_first = first_delta
        if (settled_delta > worst_settled) worst_settled = settled_delta
      }
      printf "%.3f\t%.3f\n", worst_first, worst_settled
    }
  ' $distribution

  command gawk -F '\t' '
    NR == 1 { next }
    $3 == "wsh" || $3 == "wsh-trace" {
      seen[$3]++
      if ($(NF - 1) != 1 || $NF != 1) {
        print "error: staged or detached-head trace semantics failed" > "/dev/stderr"
        exit 1
      }
    }
    END {
      if (seen["wsh"] != 1 || seen["wsh-trace"] != 1) {
        print "error: missing trace summary row" > "/dev/stderr"
        exit 2
      }
    }
  ' $summary
}

local forward_result reverse_result
forward_result=$(trace_block $forward wsh,wsh-trace)
reverse_result=$(trace_block $reverse wsh-trace,wsh)
local -F forward_first=${forward_result%%$'\t'*}
local -F forward_settled=${forward_result##*$'\t'}
local -F reverse_first=${reverse_result%%$'\t'*}
local -F reverse_settled=${reverse_result##*$'\t'}
local -F trace_first_observed=$forward_first trace_settled_observed=$forward_settled
(( reverse_first > trace_first_observed )) && trace_first_observed=$reverse_first
(( reverse_settled > trace_settled_observed )) && trace_settled_observed=$reverse_settled

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
gate_row trace-first-p90-overhead-ms '<=0.500' $(printf '%.3f' $trace_first_observed) $(( trace_first_observed > trace_first_p90_limit_ms ))
gate_row trace-settled-p90-overhead-ms '<=0.500' $(printf '%.3f' $trace_settled_observed) $(( trace_settled_observed > trace_settled_p90_limit_ms ))
gate_row retained-added-pss-p90-kib '<=4096' $memory_p90_observed $(( memory_p90_observed > memory_p90_limit_kib ))
gate_row retained-added-pss-max-kib '<=5120' $memory_max_observed $(( memory_max_observed > memory_max_limit_kib ))
(( failed == 0 ))
