#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent

(( $# == 3 )) || {
  print -u2 -- 'usage: syntax-highlighting-upstream.zsh BUNDLE SYNTAX-REPOSITORY OUTPUT'
  exit 2
}

readonly bundle=${1:A}
readonly repository=${2:A}
readonly output=${3:A}
readonly revision=2fc57d63067c18b1100ecdbf684fa5baf49459d1
[[ -x $bundle/bin/zsh && ! -e $output && ! -L $output ]] || {
  print -u2 -- 'error: bundle is invalid or output already exists'
  exit 2
}
git -C $repository cat-file -e ${revision}^{commit} 2>/dev/null || {
  print -u2 -- "error: syntax-highlighting revision is unavailable: $revision"
  exit 2
}

readonly test_root=$(mktemp -d /var/tmp/wsh-syntax-upstream.XXXXXX)
readonly upstream=$test_root/upstream
readonly candidate=$test_root/candidate
readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
trap 'command rm -rf -- $test_root $stage' EXIT INT TERM
command mkdir -p -- $upstream $candidate
git -C $repository archive $revision | tar -xf - -C $upstream
command cp -R -- $upstream/. $candidate
command cp -R -- $bundle/share/wsh/defaults/zsh-syntax-highlighting/. $candidate

make -C $upstream quiet-test ZSH=$bundle/bin/zsh > $test_root/upstream.log 2>&1
make -C $candidate quiet-test ZSH=$bundle/bin/zsh > $test_root/candidate.log 2>&1
{
  print -r -- "revision=${revision}"
  print -r -- 'variant=upstream'
  sed "s|${test_root}|<test-root>|g" $test_root/upstream.log
  print -r -- 'variant=bundled-runtime'
  sed "s|${test_root}|<test-root>|g" $test_root/candidate.log
} >| $stage

mv -- $stage $output
trap - EXIT INT TERM
command rm -rf -- $test_root
print -r -- $output
