#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent

(( $# == 2 )) || {
  print -u2 -- 'usage: summarize-native-terminal-integration.zsh RAW_TSV SUMMARY_TSV'
  exit 2
}

readonly raw=${1:A}
readonly summary=${2:A}
readonly warmups=${WSH_BENCH_WARMUPS:-5}
typeset -a variants=(native duplicate coexist)

[[ -r $raw && $warmups == <0-> ]] || {
  print -u2 -- 'error: invalid summary input'
  exit 2
}

print -r -- $'variant\truns\tp50_ms\tp90_ms\tmin_ms\tmax_ms' >| $summary
for variant in "${variants[@]}"; do
  typeset -a values=(${(f)"$(awk -F '\t' -v variant=$variant -v warmups=$warmups 'NR > 1 && $1 == variant && $2 > warmups { print $4 }' $raw | sort -n)"})
  (( $#values > 0 )) || {
    print -u2 -- "error: no retained values for ${variant}"
    exit 1
  }
  typeset -i count=$#values
  typeset -i p50_index=$(( (count * 50 + 99) / 100 ))
  typeset -i p90_index=$(( (count * 90 + 99) / 100 ))
  print -r -- "${variant}"$'\t'"${count}"$'\t'"${values[$p50_index]}"$'\t'"${values[$p90_index]}"$'\t'"${values[1]}"$'\t'"${values[-1]}" >> $summary
done

cat $summary
