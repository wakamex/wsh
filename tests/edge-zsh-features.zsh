#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

(( $# == 2 )) || {
  print -u2 -- 'usage: edge-zsh-features.zsh STABLE_BUNDLE EDGE_BUNDLE'
  exit 2
}

readonly stable_bundle=${1:A}
readonly edge_bundle=${2:A}
for bundle in $stable_bundle $edge_bundle; do
  [[ -x $bundle/bin/zsh ]] || {
    print -u2 -- "error: bundle has no Zsh executable: $bundle"
    exit 2
  }
done

[[ $($stable_bundle/bin/zsh -fc 'print -r -- $ZSH_VERSION') == 5.9.2 ]]
[[ $($edge_bundle/bin/zsh -fc 'print -r -- $ZSH_VERSION') == 5.9.999.3-test ]]

if $stable_bundle/bin/zsh -fc 'value=before; captured=${ value=after; print -r -- output }; [[ $value == after && $captured == output ]]' 2>/dev/null; then
  print -u2 -- 'stable Zsh unexpectedly accepted current-shell command substitution'
  exit 1
fi
if WSH_TEST_BUNDLE=$stable_bundle $stable_bundle/bin/zsh -fc 'module_path=("$WSH_TEST_BUNDLE/lib/zsh/$ZSH_VERSION" $module_path); zmodload zsh/ksh93' 2>/dev/null; then
  print -u2 -- 'stable Zsh unexpectedly loaded zsh/ksh93'
  exit 1
fi
[[ $($stable_bundle/bin/zsh -fc 'print -r -- ${ZSH_EXEPATH-unset}') == unset ]]

edge_result=$(WSH_TEST_BUNDLE=$edge_bundle $edge_bundle/bin/zsh -fc '
  module_path=("$WSH_TEST_BUNDLE/lib/zsh/$ZSH_VERSION" $module_path)
  value=before
  captured=${ value=after; print -r -- output }
  [[ $value == after && $captured == output ]] || exit 1
  zmodload zsh/ksh93
  value=before
  nameref reference=value
  reference=after
  [[ $value == after ]] || exit 1
  zmodload zsh/zleparameter
  typeset -gA .zle.hlgroups
  .zle.hlgroups=(warning "fg=yellow,bold")
  region_highlight=("0 1 hl=warning layer=20")
  [[ ${.zle.hlgroups[warning]} == "fg=yellow,bold" && $region_highlight[1] == "0 1 hl=warning layer=20" ]] || exit 1
  [[ $ZSH_EXEPATH == "$WSH_TEST_BUNDLE/bin/zsh" ]] || exit 1
  print -r -- edge-features-ok
')
[[ $edge_result == edge-features-ok ]]

print -r -- 'PASS: current-shell command substitution, named references, named layered highlighting, and exact executable path'
