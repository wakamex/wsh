#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

(( $# == 2 )) || {
  print -u2 -- 'usage: zcompile-reproducibility.zsh ZSH SOURCE'
  exit 2
}

readonly test_zsh=${1:A}
readonly source_file=${2:A}
readonly test_root=$(mktemp -d /var/tmp/wsh-zcompile-reproducibility.XXXXXX)

[[ -x $test_zsh && -f $source_file ]] || {
  print -u2 -- 'error: Zsh or source fixture is invalid'
  exit 2
}

cleanup() {
  command rm -rf -- $test_root
}
trap cleanup EXIT INT TERM

command mkdir -- $test_root/a $test_root/b
command cp -- $source_file $test_root/a/source.zsh
command cp -- $source_file $test_root/b/source.zsh

(
  builtin cd -q -- $test_root/a
  $test_zsh -fc 'zcompile output.zwc source.zsh'
)
(
  builtin cd -q -- $test_root/b
  $test_zsh -fc 'zcompile output.zwc source.zsh'
)

command cmp --silent $test_root/a/output.zwc $test_root/b/output.zwc || {
  print -u2 -- 'error: identical Zsh source produced different compiled bytes in isolated directories'
  exit 1
}

for dump in $test_root/{a,b}/output.zwc; do
  dump_size=$(command stat -c %s -- $dump)
  (( dump_size % 2 == 0 && dump_size >= 4 )) || {
    print -u2 -- 'error: compiled Zsh fixture has an unexpected size'
    exit 1
  }
  first_padding=$(command od -An -tx1 -j $(( dump_size / 2 - 2 )) -N 2 -- $dump | command tr -d ' \n')
  second_padding=$(command od -An -tx1 -j $(( dump_size - 2 )) -N 2 -- $dump | command tr -d ' \n')
  [[ $first_padding == 0000 && $second_padding == 0000 ]] || {
    print -u2 -- 'error: compiled Zsh dump exposes nonzero alignment padding'
    exit 1
  }
done

print -r -- 'PASS: identical Zsh source compiles byte-identically in isolated directories'
