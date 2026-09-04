#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

(( $# == 3 )) || {
  print -u2 -- 'usage: summarize-plugin-doctor.zsh BASELINE CANDIDATE OUTPUT'
  exit 2
}

readonly baseline=${1:A}
readonly candidate=${2:A}
readonly output=${3:A}
readonly expected_header=$'measured_at_utc\tblock\tposition\tvariant\trepetition\tfirst_editable_ms'
[[ -f $baseline && -f $candidate && ! -e $output && ! -L $output ]] || {
  print -u2 -- 'error: both inputs must exist and output must be new'
  exit 2
}
[[ $(head -n 1 $baseline) == $expected_header && $(head -n 1 $candidate) == $expected_header ]] || {
  print -u2 -- 'error: unexpected startup sample schema'
  exit 1
}

readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
trap 'command rm -f -- $stage' EXIT INT TERM
print -r -- $'build\tvariant\tsamples\tmedian_ms\tp90_ms\tmaximum_ms' > $stage

local build input variant
for build input in baseline $baseline candidate $candidate; do
  for variant in raw direct-complete managed-complete; do
    local -a values=(${(f)"$(awk -F '\t' -v wanted=$variant 'NR > 1 && $4 == wanted {print $6}' $input | sort -n)"})
    local -i count=${#values}
    (( count == 40 )) || {
      print -u2 -- "error: expected 40 ${build} ${variant} samples"
      exit 1
    }
    local -F median
    if (( count % 2 )); then
      median=$values[$(( (count + 1) / 2 ))]
    else
      median=$(( (values[count / 2] + values[count / 2 + 1]) / 2.0 ))
    fi
    local -i p90_index=$(( (9 * count + 9) / 10 ))
    printf '%s\t%s\t%d\t%.6f\t%.6f\t%.6f\n' $build $variant $count $median $values[$p90_index] $values[-1] >> $stage
  done
done

mv -- $stage $output
trap - EXIT INT TERM
print -r -- $output
