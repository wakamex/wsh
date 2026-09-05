#!/usr/bin/env zsh

emulate -L zsh -o errexit -o nounset -o pipefail

(( $# == 2 )) || {
  print -u2 -- 'usage: summarize-profile.zsh INPUT OUTPUT'
  exit 2
}

readonly input=${1:A}
readonly output=${2:A}
[[ $(head -n 1 $input) == $'measured_at_utc\tblock\tposition\tvariant\trepetition\tfirst_editable_ms\tsettled_ms' ]]
[[ ! -e $output && ! -L $output ]]
readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
trap 'rm -f -- $stage' EXIT INT TERM

print -r -- $'metric\tvariant\tsamples\tmedian_ms\tp90_ms\tmaximum_ms' > $stage
awk -F '\t' '
  NR > 1 {
    first[$4, ++first_count[$4]] = $6
    settled[$4, ++settled_count[$4]] = $7
    key = $2 SUBSEP $5
    pair_first[key, $4] = $6
    pair_refresh[key, $4] = $7 - $6
    pair_keys[key] = 1
  }
  function emit(metric, variant, values, count,    i, j, temporary, rank) {
    for (i = 1; i <= count; i++) sorted[i] = values[variant, i]
    for (i = 2; i <= count; i++) {
      temporary = sorted[i]
      j = i - 1
      while (j >= 1 && sorted[j] > temporary) { sorted[j + 1] = sorted[j]; j-- }
      sorted[j + 1] = temporary
    }
    rank = int(0.9 * count + 0.999999)
    printf "%s\t%s\t%d\t%.6f\t%.6f\t%.6f\n", metric, variant, count, sorted[int((count + 1) / 2)], sorted[rank], sorted[count]
    delete sorted
  }
  END {
    emit("first-editable", "normal", first, first_count["normal"])
    emit("first-editable", "profile", first, first_count["profile"])
    emit("settled", "normal", settled, settled_count["normal"])
    emit("settled", "profile", settled, settled_count["profile"])
    for (key in pair_keys) {
      if ((key SUBSEP "normal") in pair_first && (key SUBSEP "profile") in pair_first) {
        first_overhead["paired", ++first_overhead_count] = pair_first[key, "profile"] - pair_first[key, "normal"]
        refresh_overhead["paired", ++refresh_overhead_count] = pair_refresh[key, "profile"] - pair_refresh[key, "normal"]
      }
    }
    emit("first-editable-overhead", "paired", first_overhead, first_overhead_count)
    emit("refresh-overhead-diagnostic", "paired", refresh_overhead, refresh_overhead_count)
  }
' $input >> $stage

mv -- $stage $output
trap - EXIT INT TERM
print -r -- $output
