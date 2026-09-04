#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

(( $# == 2 )) || {
  print -u2 -- 'usage: summarize-foreground-startup.zsh INPUT OUTPUT'
  exit 2
}

readonly input=${1:A}
readonly output=${2:A}
readonly expected_header=$'measured_at_utc\tblock\tposition\tvariant\trepetition\tpty_to_ready_ms\tready_to_prompt_ms'
[[ -f $input && ! -e $output && ! -L $output && $(head -n 1 $input) == $expected_header ]] || {
  print -u2 -- 'error: input must use the foreground-startup schema and output must be new'
  exit 2
}

readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
trap 'command rm -f -- $stage' EXIT INT TERM
print -r -- $'variant\tmetric\tsamples\tmedian_ms\tp90_ms\tmaximum_ms' > $stage

local variant metric column
for variant in current positional candidate; do
  for metric column in pty-to-ready 6 ready-to-prompt 7; do
    local -a values=(${(f)"$(awk -F '\t' -v wanted=$variant -v column=$column 'NR > 1 && $4 == wanted {print $column}' $input | sort -n)"})
    local -i count=${#values}
    (( count == 40 )) || {
      print -u2 -- "error: expected 40 ${variant} ${metric} samples"
      exit 1
    }
    local -F median=$(( (values[count / 2] + values[count / 2 + 1]) / 2.0 ))
    local -i p90_index=$(( (9 * count + 9) / 10 ))
    printf '%s\t%s\t%d\t%.6f\t%.6f\t%.6f\n' $variant $metric $count $median $values[$p90_index] $values[-1] >> $stage
  done
done

mv -- $stage $output
trap - EXIT INT TERM
print -r -- $output
