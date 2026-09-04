#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent

(( $# == 2 )) || {
  print -u2 -- 'usage: plugin-doctor.zsh MANAGER BUNDLE'
  exit 2
}

readonly manager=${1:A}
readonly bundle=${2:A}
readonly test_root=$(mktemp -d /var/tmp/wsh-plugin-doctor.XXXXXX)
readonly state_root=$test_root/state
readonly exact_history=$bundle/share/wsh/defaults/zsh-history-substring-search.zsh
readonly omz_history=$bundle/share/wsh/defaults/known-oh-my-zsh-history-substring-search.zsh
readonly exact_autosuggestions=$bundle/share/wsh/defaults/zsh-autosuggestions.zsh
readonly exact_syntax=$bundle/share/wsh/defaults/zsh-syntax-highlighting
readonly modified_history=$test_root/modified-history.zsh
readonly modified_autosuggestions=$test_root/modified-autosuggestions.zsh
readonly modified_syntax=$test_root/modified-syntax

[[ -x $manager && -x $bundle/bin/zsh && -f $exact_history && -f $omz_history && -f $exact_autosuggestions && -f $exact_syntax/zsh-syntax-highlighting.zsh ]] || {
  print -u2 -- 'error: manager or complete plugin bundle is invalid'
  exit 2
}

cleanup() {
  command rm -rf -- $test_root
}
trap cleanup EXIT INT TERM

command mkdir -p -- $test_root
command cp -- $exact_history $modified_history
command cp -- $exact_autosuggestions $modified_autosuggestions
command cp -R -- $exact_syntax $modified_syntax
print -r -- '# modified doctor fixture' >> $modified_history
print -r -- '# modified doctor fixture' >> $modified_autosuggestions
print -r -- '# modified doctor fixture' >> $modified_syntax/highlighters/main/main-highlighter.zsh
$manager bundle activate $bundle --state-root $state_root >/dev/null

write_home() {
  local variant=$1
  local home=$test_root/home-$variant
  command mkdir -p -- $home
  local config=$home/.zshrc
  : >| $config
  case $variant in
    clean) ;;
    exact)
      print -r -- "source ${(q)exact_history}
source ${(q)exact_autosuggestions}
zmodload zsh/zle
source ${(q)exact_syntax}/zsh-syntax-highlighting.zsh" >> $config
      ;;
    omz-history)
      print -r -- "source ${(q)omz_history}" >> $config
      ;;
    active-autosuggestions)
      print -r -- "source ${(q)exact_autosuggestions}
typeset -gA _ZSH_AUTOSUGGEST_BIND_COUNTS=(self-insert 1)" >> $config
      ;;
    modified)
      print -r -- "source ${(q)modified_history}
source ${(q)modified_autosuggestions}
zmodload zsh/zle
source ${(q)modified_syntax}/zsh-syntax-highlighting.zsh" >> $config
      ;;
    disabled)
      print -r -- "typeset -g WSH_DISABLE_HISTORY_SUBSTRING_SEARCH=1
typeset -g WSH_DISABLE_AUTOSUGGESTIONS=1
typeset -g WSH_DISABLE_SYNTAX_HIGHLIGHTING=1
source ${(q)exact_history}
source ${(q)exact_autosuggestions}
zmodload zsh/zle
source ${(q)exact_syntax}/zsh-syntax-highlighting.zsh" >> $config
      ;;
  esac
  print -r -- $home
}

run_doctor() {
  local home=$1 output=$2
  local before=$(sha256sum $home/.zshrc)
  HOME=$home ZDOTDIR=$home WSH_STATE_ROOT=$state_root \
    $manager doctor --state-root $state_root >| $output
  local after=$(sha256sum $home/.zshrc)
  [[ $before == $after ]] || {
    print -u2 -- "error: doctor changed ${home}/.zshrc"
    return 1
  }
}

local home output
home=$(write_home clean)
output=$test_root/clean.out
run_doctor $home $output
[[ $(<$output) == 'Plugin compatibility: no redundant or unrecognized external implementations detected.' ]]

home=$(write_home exact)
output=$test_root/exact.out
run_doctor $home $output
for component in zsh-history-substring-search zsh-autosuggestions zsh-syntax-highlighting; do
  grep -F -- "- ${component}: an exact external copy is redundant." $output >/dev/null
done
[[ $(grep -c 'Remove its startup declaration' $output) == 3 ]]

home=$(write_home omz-history)
output=$test_root/omz-history.out
run_doctor $home $output
grep -F -- '- zsh-history-substring-search: an exact external copy is redundant.' $output >/dev/null
[[ $(grep -c 'Remove its startup declaration' $output) == 1 ]]

home=$(write_home active-autosuggestions)
output=$test_root/active-autosuggestions.out
run_doctor $home $output
grep -F -- '- zsh-autosuggestions: an exact external copy is redundant.' $output >/dev/null

home=$(write_home modified)
output=$test_root/modified.out
run_doctor $home $output
for component in zsh-history-substring-search zsh-autosuggestions zsh-syntax-highlighting; do
  grep -F -- "- ${component}: a modified or unrecognized external implementation was preserved." $output >/dev/null
done
! grep -F -- 'Remove its startup declaration' $output >/dev/null

home=$(write_home disabled)
output=$test_root/disabled.out
run_doctor $home $output
[[ $(<$output) == 'Plugin compatibility: no redundant or unrecognized external implementations detected.' ]]

print -r -- 'PASS: plugin doctor diagnoses exact and unknown implementations without modifying startup files'
