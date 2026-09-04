#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

(( $# == 2 )) || {
  print -u2 -- 'usage: summarize-edge-zsh.zsh EVIDENCE_DIRECTORY OUTPUT'
  exit 2
}

readonly evidence=${1:A}
readonly output=${2:A}
[[ -d $evidence && ! -e $output && ! -L $output ]] || {
  print -u2 -- 'error: evidence directory must exist and output must be new'
  exit 2
}

readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
readonly final=$(mktemp "${output:h}/.${output:t}.XXXXXX")
trap 'command rm -f -- $stage $final' EXIT INT TERM
print -r -- $'measurement\tbuild\tconfiguration\tworkload\tsamples\tmedian\tp90\tmaximum\tunit' > $stage

gawk -F '\t' '
  function emit(k, p, count, middle, rank) {
    split(k, p, SUBSEP); delete sorted
    for (i = 1; i <= counts[k]; i++) sorted[i] = values[k, i]
    asort(sorted); middle = int(counts[k] / 2); rank = int((9 * counts[k] + 9) / 10)
    median = counts[k] % 2 ? sorted[middle + 1] : (sorted[middle] + sorted[middle + 1]) / 2
    printf "raw-process-startup\t%s\tshell\texit\t%d\t%.6f\t%.6f\t%.6f\tmicroseconds\n", p[1], counts[k], median, sorted[rank], sorted[counts[k]]
  }
  NR > 1 { key = $4; values[key, ++counts[key]] = $10 + 0 }
  END { for (key in counts) emit(key) }
' $evidence/raw-process-startup.tsv >> $stage

gawk -F '\t' '
  function emit(k, p, middle, rank) {
    split(k, p, SUBSEP); delete sorted
    for (i = 1; i <= counts[k]; i++) sorted[i] = values[k, i]
    asort(sorted); middle = int(counts[k] / 2); rank = int((9 * counts[k] + 9) / 10)
    median = counts[k] % 2 ? sorted[middle + 1] : (sorted[middle] + sorted[middle + 1]) / 2
    printf "first-editable\t%s\t%s\tinitial\t%d\t%.6f\t%.6f\t%.6f\tms\n", p[2], p[1], counts[k], median, sorted[rank], sorted[counts[k]]
  }
  NR > 1 { split($4, part, "-"); key = part[1] SUBSEP part[2]; values[key, ++counts[key]] = $6 + 0 }
  END { for (key in counts) emit(key) }
' $evidence/first-editable.tsv >> $stage

gawk -F '\t' '
  function emit(k, p, middle, rank) {
    split(k, p, SUBSEP); delete sorted
    for (i = 1; i <= counts[k]; i++) sorted[i] = values[k, i]
    asort(sorted); middle = int(counts[k] / 2); rank = int((9 * counts[k] + 9) / 10)
    median = counts[k] % 2 ? sorted[middle + 1] : (sorted[middle] + sorted[middle + 1]) / 2
    printf "interactive-default-startup\t%s\t%s\tinitial\t%d\t%.6f\t%.6f\t%.6f\tms\n", p[1], p[2], counts[k], median, sorted[rank], sorted[counts[k]]
  }
  NR > 1 { key = $2 SUBSEP $5; values[key, ++counts[key]] = $7 + 0 }
  END { for (key in counts) emit(key) }
' $evidence/defaults-startup.tsv >> $stage

for build in stable edge; do
  gawk -F '\t' -v build=$build '
    function emit(k, middle, rank) {
      delete sorted; for (i = 1; i <= counts[k]; i++) sorted[i] = values[k, i]
      asort(sorted); middle = int(counts[k] / 2); rank = int((9 * counts[k] + 9) / 10)
      median = counts[k] % 2 ? sorted[middle + 1] : (sorted[middle] + sorted[middle + 1]) / 2
      printf "autosuggestion-prompt\t%s\t%s\tsettled\t%d\t%.6f\t%.6f\t%.6f\tms\n", build, k, counts[k], median, sorted[rank], sorted[counts[k]]
    }
    NR > 1 { key = $5; values[key, ++counts[key]] = $7 + 0 }
    END { for (key in counts) emit(key) }
  ' $evidence/autosuggestions-prompt-$build.tsv >> $stage
  gawk -F '\t' -v build=$build '
    function emit(k, metric, column, middle, rank) {
      delete sorted; for (i = 1; i <= counts[k]; i++) sorted[i] = values[k, i, column]
      asort(sorted); middle = int(counts[k] / 2); rank = int((9 * counts[k] + 9) / 10)
      median = counts[k] % 2 ? sorted[middle + 1] : (sorted[middle] + sorted[middle + 1]) / 2
      printf "%s\t%s\t%s\tedit\t%d\t%.6f\t%.6f\t%.6f\tms\n", metric, build, k, counts[k], median, sorted[rank], sorted[counts[k]]
    }
    NR > 1 { key = $5; row = ++counts[key]; values[key, row, 7] = $7 + 0; values[key, row, 8] = $8 + 0 }
    END { for (key in counts) { emit(key, "autosuggestion-visible", 7); emit(key, "autosuggestion-accept", 8) } }
  ' $evidence/autosuggestions-edit-$build.tsv >> $stage
done

gawk -F '\t' '
  function emit(k, p, middle, rank) {
    split(k, p, SUBSEP); delete sorted
    for (i = 1; i <= counts[k]; i++) sorted[i] = values[k, i]
    asort(sorted); middle = int(counts[k] / 2); rank = int((9 * counts[k] + 9) / 10)
    median = counts[k] % 2 ? sorted[middle + 1] : (sorted[middle] + sorted[middle + 1]) / 2
    printf "syntax-highlight-redraw\t%s\tbundled\t%s\t%d\t%.6f\t%.6f\t%.6f\tms\n", p[1], p[2], counts[k], median, sorted[rank], sorted[counts[k]]
  }
  NR > 1 { key = $2 SUBSEP $5; values[key, ++counts[key]] = $7 + 0 }
  END { for (key in counts) emit(key) }
' $evidence/syntax-internal.tsv >> $stage

for build in stable edge; do
  gawk -F '\t' -v build=$build '
    function emit(column, name, middle, rank) {
      delete sorted; for (i = 1; i <= count; i++) sorted[i] = values[column, i]
      asort(sorted); middle = int(count / 2); rank = int((9 * count + 9) / 10)
      median = count % 2 ? sorted[middle + 1] : (sorted[middle] + sorted[middle + 1]) / 2
      printf "retained-memory\t%s\t%s\tsettled\t%d\t%.6f\t%.6f\t%.6f\tKiB\n", build, name, count, median, sorted[rank], sorted[count]
    }
    NR > 1 { count++; values[3, count] = $3 + 0; values[6, count] = $6 + 0; values[7, count] = $7 + 0 }
    END { emit(3, "raw-zsh"); emit(6, "wsh-combined"); emit(7, "wsh-added") }
  ' $evidence/memory-$build.tsv >> $stage
done

for renderer in minimal wakamex; do
  for build in stable edge; do
    target=wsh
    [[ $renderer == wakamex ]] && target=wsh-wakamex
    gawk -F '\t' -v build=$build -v renderer=$renderer -v target=$target '
      function emit(k, column, suffix, p, middle, rank) {
        split(k, p, SUBSEP); delete sorted
        for (i = 1; i <= counts[k]; i++) sorted[i] = values[k, i, column]
        asort(sorted); middle = int(counts[k] / 2); rank = int((9 * counts[k] + 9) / 10)
        median = counts[k] % 2 ? sorted[middle + 1] : (sorted[middle] + sorted[middle + 1]) / 2
        printf "git-prompt-%s\t%s\t%s-%s\t%s\t%d\t%.6f\t%.6f\t%.6f\tms\n", suffix, build, renderer, p[1], p[2], counts[k], median, sorted[rank], sorted[counts[k]]
      }
      FNR > 1 && ($4 == "raw" || $4 == target) {
        kind = $4 == "raw" ? "raw" : "wsh"; key = kind SUBSEP $12; row = ++counts[key]
        values[key, row, 14] = $14 + 0; values[key, row, 15] = $15 + 0
      }
      END { for (key in counts) { emit(key, 14, "first"); emit(key, 15, "settled") } }
    ' $evidence/$renderer-final-$build-forward/samples.tsv $evidence/$renderer-final-$build-reverse/samples.tsv >> $stage
  done
done

sed -i '1d' $stage
LC_ALL=C sort -t $'\t' -k1,1 -k2,2 -k3,3 -k4,4 $stage -o $stage
print -r -- $'measurement\tbuild\tconfiguration\tworkload\tsamples\tmedian\tp90\tmaximum\tunit' > $final
while IFS= read -r row; do
  print -r -- $row >> $final
done < $stage
mv -- $final $output
trap - EXIT INT TERM
command rm -f -- $stage
print -r -- $output
