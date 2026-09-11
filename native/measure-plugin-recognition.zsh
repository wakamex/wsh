#!/usr/bin/env zsh
# Same-shell, same-file comparison with no process-launch timing in the clock.
builtin emulate -L zsh -o no_aliases -o err_return
readonly WSH_BUNDLE_ROOT=${1:A}
readonly source_file=${2:A}
source $WSH_BUNDLE_ROOT/share/wsh/defaults/plugin-recognition.zsh
zmodload zsh/datetime
local pair variant before elapsed
for pair in {1..50}; do
  local -a order=(catalog git)
  (( pair % 2 )) || order=(git catalog)
  for variant in $order; do
    before=$EPOCHREALTIME
    if [[ $variant == catalog ]]; then
      _wsh_plugin_recognized autosuggestions $source_file
    else
      _wsh_plugin_git_recognized autosuggestions $source_file
    fi
    elapsed=$(( (EPOCHREALTIME - before) * 1000 ))
    print -r -- "$pair $variant $elapsed"
  done
done
