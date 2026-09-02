#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

local root=${0:A:h:h}
local evidence=${1:-${root}/benchmarks/resource-gates-2026-09-02}
local metadata=${evidence}/metadata.txt

for command in cmp git gawk sha256sum; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    return 2
  }
done
[[ -r $metadata ]] || {
  print -u2 -- "error: resource-gate metadata is unavailable: $metadata"
  return 2
}

typeset -A recorded
local line key value
while IFS= read -r line; do
  [[ $line == *=* ]] || {
    print -u2 -- "error: malformed resource-gate metadata line: $line"
    return 2
  }
  key=${line%%=*}
  value=${line#*=}
  recorded[$key]=$value
done < $metadata
[[ ${recorded[accepted]:-} == 1 ]] || {
  print -u2 -- 'error: resource-gate evidence is not marked accepted'
  return 1
}
git -C $root cat-file -e ${recorded[source_revision]:-missing}^{commit} 2>/dev/null || {
  print -u2 -- 'error: recorded resource-gate source revision is unavailable'
  return 1
}

verify_digest() {
  local metadata_key=$1 file=$2 actual
  actual=$(sha256sum $file)
  actual=${actual%% *}
  [[ $actual == ${recorded[$metadata_key]:-} ]] || {
    print -u2 -- "error: $file digest is $actual; metadata records ${recorded[$metadata_key]:-missing}"
    return 1
  }
}

verify_digest trace_runner_sha256 ${root}/benchmarks/benchmark-trace-overhead.zsh
verify_digest memory_runner_sha256 ${root}/benchmarks/benchmark-runtime-memory.zsh
verify_digest gate_checker_sha256 ${root}/benchmarks/check-resource-gates.zsh
verify_digest trace_sha256 ${evidence}/trace.tsv
verify_digest memory_sha256 ${evidence}/memory.tsv
verify_digest gates_sha256 ${evidence}/gates.tsv

local generated=${evidence}/.verified-gates.$$.tsv
trap 'command rm -f -- $generated' EXIT INT TERM
${root}/benchmarks/check-resource-gates.zsh ${evidence}/memory.tsv ${evidence}/trace.tsv > $generated
cmp --silent $generated ${evidence}/gates.tsv || {
  print -u2 -- 'error: retained resource-gate summary does not match its raw inputs'
  return 1
}

print -r -- 'PASS: retained resource-gate inputs, implementation digests, and summary agree'
