#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent

(( $# == 3 )) || {
  print -u2 -- 'usage: trace-native-terminal-integration.zsh ZSH WAKTERM_INTEGRATION OUTPUT_DIRECTORY'
  exit 2
}

readonly root=${0:A:h:h}
readonly zsh_binary=${1:A}
readonly wakterm_integration=${2:A}
readonly output=${3:A}

[[ -x $zsh_binary && -r $wakterm_integration && ! -e $output ]] || {
  print -u2 -- 'error: invalid input or output directory already exists'
  exit 2
}
for command in awk find sha256sum sort strace xargs; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: ${command}"
    exit 2
  }
done

mkdir -p -- $output
print -r -- $'variant\texecve_calls\twakterm_set_working_directory_calls' >| $output/process-summary.tsv

for variant in native duplicate coexist; do
  variant_dir=$output/$variant
  mkdir -p -- $variant_dir
  strace -ff -qq -e trace=process -o $variant_dir/trace \
    $zsh_binary -f $root/tests/native-terminal-integration.zsh $zsh_binary $wakterm_integration $variant $variant_dir/transcript.bin \
    >| $variant_dir/counts.tsv
  execve_calls=$(awk '/execve\(/ { count++ } END { print count + 0 }' $variant_dir/trace.*)
  wakterm_calls=$(awk 'index($0, "[\"wakterm\", \"set-working-directory\"]") { count++ } END { print count + 0 }' $variant_dir/trace.*)
  print -r -- "${variant}"$'\t'"${execve_calls}"$'\t'"${wakterm_calls}" >> $output/process-summary.tsv
done

(builtin cd -q $output && find . -type f ! -name files.sha256 -print0 | sort -z | xargs -0 sha256sum >| files.sha256)

print -r -- 'PASS: captured native, duplicate, and accepted coexistence process traces'
