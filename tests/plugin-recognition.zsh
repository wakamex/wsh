#!/usr/bin/env zsh
builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
readonly WSH_BUNDLE_ROOT=${1:A}
readonly root=${0:A:h:h}
readonly temporary=$(mktemp -d /var/tmp/wsh-plugin-recognition.XXXXXX)
trap 'rm -rf -- $temporary' EXIT
source $WSH_BUNDLE_ROOT/share/wsh/defaults/plugin-recognition.zsh
local source=$WSH_BUNDLE_ROOT/share/wsh/defaults/known-zsh-autosuggestions-0.7.0.zsh
_wsh_plugin_recognized autosuggestions $source
! _wsh_plugin_recognized missing $source
! _wsh_plugin_recognized autosuggestions
! _wsh_plugin_files_equal $source
! _wsh_plugin_files_equal
! _wsh_plugin_recognized syntax $source
cp -- $source "$temporary/copy with spaces.zsh"
_wsh_plugin_recognized autosuggestions "$temporary/copy with spaces.zsh"
print -r -- '# customized' >> "$temporary/copy with spaces.zsh"
! _wsh_plugin_recognized autosuggestions "$temporary/copy with spaces.zsh"
: > $temporary/empty
! _wsh_plugin_recognized autosuggestions $temporary/empty
! _wsh_plugin_recognized autosuggestions $temporary/missing
! _wsh_plugin_recognized autosuggestions $temporary
python3 - "$temporary/large" <<'PY'
import sys
from pathlib import Path
Path(sys.argv[1]).write_bytes(b'x' * 131073)
PY
! _wsh_plugin_files_equal $temporary/large $temporary/large
local syntax=$WSH_BUNDLE_ROOT/share/wsh/defaults/zsh-syntax-highlighting
_wsh_plugin_recognized syntax $syntax/zsh-syntax-highlighting.zsh $syntax/highlighters/main/known-main-highlighter.zsh
! _wsh_plugin_recognized syntax $syntax/zsh-syntax-highlighting.zsh $syntax/recognized/b2c910a/main-highlighter.zsh
print -r -- 'PASS: catalog arity, missing/empty/large files, paths, modification and mixed-version rejection'
