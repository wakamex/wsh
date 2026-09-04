#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

(( $# == 2 )) || {
  print -u2 -- 'usage: summarize-managed-builds.zsh INPUT OUTPUT'
  exit 2
}

readonly input=${1:A}
readonly output=${2:A}
readonly expected_header=$'measured_at_utc\tblock\tposition\tbuild\trepetition\tfirst_editable_ms'
[[ -f $input && ! -e $output && ! -L $output && $(head -n 1 $input) == $expected_header ]] || {
  print -u2 -- 'error: input must use the managed-build schema and output must be new'
  exit 2
}

readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
trap 'command rm -f -- $stage' EXIT INT TERM
print -r -- $'build\tsamples\tmedian_ms\tp90_ms\tmaximum_ms' > $stage

local build
for build in baseline candidate; do
  local -a values=(${(f)"$(awk -F '\t' -v wanted=$build 'NR > 1 && $4 == wanted {print $6}' $input | sort -n)"})
  local -i count=${#values}
  (( count == 40 )) || {
    print -u2 -- "error: expected 40 ${build} samples"
    exit 1
  }
  local -F median=$(( (values[count / 2] + values[count / 2 + 1]) / 2.0 ))
  local -i p90_index=$(( (9 * count + 9) / 10 ))
  printf '%s\t%d\t%.6f\t%.6f\t%.6f\n' $build $count $median $values[$p90_index] $values[-1] >> $stage
done

mv -- $stage $output
trap - EXIT INT TERM
print -r -- $output
