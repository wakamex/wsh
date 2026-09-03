#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent

(( $# == 7 )) || {
  print -u2 -- 'usage: summarize-autosuggestions.zsh STARTUP-BASELINE STARTUP-CANDIDATE PROMPT-BASELINE PROMPT-CANDIDATE EDIT-BASELINE EDIT-CANDIDATE OUTPUT'
  exit 2
}

readonly startup_baseline=${1:A}
readonly startup_candidate=${2:A}
readonly prompt_baseline=${3:A}
readonly prompt_candidate=${4:A}
readonly edit_baseline=${5:A}
readonly edit_candidate=${6:A}
readonly output=${7:A}
for input in $startup_baseline $startup_candidate $prompt_baseline $prompt_candidate $edit_baseline $edit_candidate; do
  [[ -f $input ]] || {
    print -u2 -- "error: input does not exist: $input"
    exit 2
  }
done
[[ ! -e $output && ! -L $output ]] || {
  print -u2 -- 'error: output must be new'
  exit 2
}

readonly startup_header=$'measured_at_utc\tbuild\tblock\tposition\tvariant\trepetition\tfirst_editable_ms'
readonly prompt_header=$'measured_at_utc\tbuild\tblock\tposition\tvariant\trepetition\tprompt_ms'
readonly edit_header=$'measured_at_utc\tbuild\tblock\tposition\tvariant\trepetition\tavailable_ms\taccepted_ms'
[[ $(head -n 1 $startup_baseline) == $startup_header && $(head -n 1 $startup_candidate) == $startup_header ]] || {
  print -u2 -- 'error: unexpected startup sample schema'
  exit 1
}
[[ $(head -n 1 $prompt_baseline) == $prompt_header && $(head -n 1 $prompt_candidate) == $prompt_header ]] || {
  print -u2 -- 'error: unexpected prompt sample schema'
  exit 1
}
[[ $(head -n 1 $edit_baseline) == $edit_header && $(head -n 1 $edit_candidate) == $edit_header ]] || {
  print -u2 -- 'error: unexpected edit sample schema'
  exit 1
}

readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
trap 'command rm -f -- $stage' EXIT INT TERM
print -r -- $'measurement\tbuild\tvariant\tsamples\tmedian_ms\tp90_ms\tmaximum_ms' > $stage

summarize_column() {
  local measurement=$1 build=$2 input=$3 column=$4
  local -a variants=(${(f)"$(tail -n +2 $input | cut -f5 | sort -u)"})
  local variant
  for variant in $variants; do
    local -a values=(${(f)"$(awk -F '\t' -v wanted=$variant -v column=$column 'NR > 1 && $5 == wanted {print $column}' $input | sort -n)"})
    local -i count=${#values}
    (( count > 0 )) || continue
    local -F median
    if (( count % 2 )); then
      median=$values[$(( (count + 1) / 2 ))]
    else
      median=$(( (values[count / 2] + values[count / 2 + 1]) / 2.0 ))
    fi
    local -i p90_index=$(( (9 * count + 9) / 10 ))
    printf '%s\t%s\t%s\t%d\t%.6f\t%.6f\t%.6f\n' $measurement $build $variant $count $median $values[$p90_index] $values[-1] >> $stage
  done
}

summarize_column first-editable baseline $startup_baseline 7
summarize_column first-editable candidate $startup_candidate 7
summarize_column settled-prompt baseline $prompt_baseline 7
summarize_column settled-prompt candidate $prompt_candidate 7
summarize_column suggestion-available baseline $edit_baseline 7
summarize_column suggestion-available candidate $edit_candidate 7
summarize_column suggestion-accepted baseline $edit_baseline 8
summarize_column suggestion-accepted candidate $edit_candidate 8

mv -- $stage $output
trap - EXIT INT TERM
print -r -- $output
