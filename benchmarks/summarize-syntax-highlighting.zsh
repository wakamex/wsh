#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent

(( $# == 4 )) || {
  print -u2 -- 'usage: summarize-syntax-highlighting.zsh STARTUP EDIT-BASELINE EDIT-CANDIDATE OUTPUT'
  exit 2
}

readonly startup=${1:A}
readonly edit_baseline=${2:A}
readonly edit_candidate=${3:A}
readonly output=${4:A}
for input in $startup $edit_baseline $edit_candidate; do
  [[ -f $input ]] || { print -u2 -- "error: input does not exist: $input"; exit 2; }
done
[[ ! -e $output && ! -L $output ]] || { print -u2 -- 'error: output must be new'; exit 2; }

readonly startup_header=$'measured_at_utc\tbuild\tblock\tposition\tvariant\trepetition\tfirst_editable_ms'
readonly edit_header=$'measured_at_utc\tbuild\tblock\tposition\tvariant\tworkload\trepetition\tredraw_ms'
[[ $(head -n 1 $startup) == $startup_header ]] || { print -u2 -- 'error: unexpected startup schema'; exit 1; }
[[ $(head -n 1 $edit_baseline) == $edit_header && $(head -n 1 $edit_candidate) == $edit_header ]] || { print -u2 -- 'error: unexpected edit schema'; exit 1; }

readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
trap 'command rm -f -- $stage' EXIT INT TERM
print -r -- $'measurement\tbuild\tvariant\tworkload\tsamples\tmedian_ms\tp90_ms\tmaximum_ms' > $stage

summarize() {
  local measurement=$1 build=$2 input=$3 column=$4 workload_column=$5
  local -a variants=(${(f)"$(tail -n +2 $input | cut -f5 | sort -u)"})
  local variant workload
  for variant in $variants; do
    local -a workloads=(-)
    (( workload_column )) && workloads=(${(f)"$(awk -F '\t' -v wanted=$variant 'NR > 1 && $5 == wanted {print $6}' $input | sort -u)"})
    for workload in $workloads; do
      local -a values
      if (( workload_column )); then
        values=(${(f)"$(awk -F '\t' -v wanted=$variant -v workload=$workload -v column=$column 'NR > 1 && $5 == wanted && $6 == workload {print $column}' $input | sort -n)"})
      else
        values=(${(f)"$(awk -F '\t' -v wanted=$variant -v column=$column 'NR > 1 && $5 == wanted {print $column}' $input | sort -n)"})
      fi
      local -i count=${#values}
      (( count > 0 )) || continue
      local -F median
      if (( count % 2 )); then
        median=$values[$(( (count + 1) / 2 ))]
      else
        median=$(( (values[count / 2] + values[count / 2 + 1]) / 2.0 ))
      fi
      local -i p90_index=$(( (9 * count + 9) / 10 ))
      printf '%s\t%s\t%s\t%s\t%d\t%.6f\t%.6f\t%.6f\n' $measurement $build $variant $workload $count $median $values[$p90_index] $values[-1] >> $stage
    done
  done
}

local build variant
for build in baseline candidate; do
  local -a variants=(${(f)"$(awk -F '\t' -v build=$build 'NR > 1 && $2 == build {print $5}' $startup | sort -u)"})
  for variant in $variants; do
    local -a values=(${(f)"$(awk -F '\t' -v build=$build -v wanted=$variant 'NR > 1 && $2 == build && $5 == wanted {print $7}' $startup | sort -n)"})
    local -i count=${#values}
    local -F median
    if (( count % 2 )); then
      median=$values[$(( (count + 1) / 2 ))]
    else
      median=$(( (values[count / 2] + values[count / 2 + 1]) / 2.0 ))
    fi
    local -i p90_index=$(( (9 * count + 9) / 10 ))
    printf 'first-editable\t%s\t%s\t-\t%d\t%.6f\t%.6f\t%.6f\n' $build $variant $count $median $values[$p90_index] $values[-1] >> $stage
  done
done
summarize redraw baseline $edit_baseline 8 1
summarize redraw candidate $edit_candidate 8 1

mv -- $stage $output
trap - EXIT INT TERM
print -r -- $output
