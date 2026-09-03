#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

(( $# == 2 )) || {
  print -u2 -- 'usage: summarize-config-startup.zsh INPUT OUTPUT'
  exit 2
}

readonly input=${1:A}
readonly output=${2:A}
[[ -f $input && ! -e $output && ! -L $output ]] || {
  print -u2 -- 'error: input must exist and output must be new'
  exit 2
}
[[ $(head -n 1 $input) == $'measured_at_utc\tblock\tposition\tvariant\trepetition\tfirst_editable_ms' ]] || {
  print -u2 -- 'error: unexpected startup sample schema'
  exit 1
}

readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
trap 'command rm -f -- $stage' EXIT INT TERM
print -r -- $'variant\tsamples\tmedian_ms\tp90_ms\tmaximum_ms' > $stage

local variant
local -a variants=(${(f)"$(tail -n +2 $input | cut -f4 | sort -u)"})
for variant in $variants; do
  local -a values=(${(f)"$(awk -F '\t' -v wanted=$variant 'NR > 1 && $4 == wanted {print $6}' $input | sort -n)"})
  local -i count=${#values}
  (( count > 0 )) || continue
  local -F median
  if (( count % 2 )); then
    median=$values[$(( (count + 1) / 2 ))]
  else
    median=$(( (values[count / 2] + values[count / 2 + 1]) / 2.0 ))
  fi
  local -i p90_index=$(( (9 * count + 9) / 10 ))
  printf '%s\t%d\t%.6f\t%.6f\t%.6f\n' $variant $count $median $values[$p90_index] $values[-1] >> $stage
done

mv -- $stage $output
trap - EXIT INT TERM
print -r -- $output
