#!/usr/bin/env python3
"""Compare native-owned editor state and visible search regions with the pinned plugin."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
binary, module, out = [Path(p).resolve() for p in sys.argv[1:4]]
mode = sys.argv[4]
out.mkdir(parents=True, exist_ok=True)
source = (root / 'third_party/zsh-history-substring-search/zsh-history-substring-search.zsh').read_text()
(out / 'control.zsh').write_text(source)
a = source.index('typeset -g BUFFER')
b = source.index('#-----------------------------------------------------------------------------\n# implementation details', a)
source = source[:a] + '''typeset -gi _history_substring_search_zsh_5_9=1
history-substring-search-up() { builtin wsh-history up }
history-substring-search-down() { builtin wsh-history down }
zle -N history-substring-search-up
zle -N history-substring-search-down

''' + source[b:source.index('_history-substring-search-begin() {')]
(out / 'candidate.zsh').write_text(source)
if module.name == 'installed':
    (out / 'candidate.zsh').write_bytes((binary.parent.parent / 'share/wsh/defaults/native-history.zsh').read_bytes())
harness = (root / 'native/test-history-navigation-zle.py').read_text()
if module.name == 'installed':
    harness = harness.replace('zmodload wshhistory', ':')
harness = harness.replace('ROOT=Path(__file__).resolve().parents[1]', 'ROOT=Path(' + repr(str(root)) + ')')
harness = harness.replace("  _history_substring_search_result=''", "  _history_substring_search_result=''\n  builtin wsh-history reset\n  captured_regions=()")
if mode == 'correctness':
    harness = harness.replace("('','','1')]:", "('','','1'),('','','ignoredups'),('','','findnodups'),('','','prefix'),('','','case-sensitive'),('1','1',''),('','','nohighlight')]:")
    harness = harness.replace("[[ $WSH_TEST_VI == 1 ]] && bindkey -v", """[[ $WSH_TEST_VI == 1 ]] && bindkey -v
case $WSH_TEST_VI in
  ignoredups) setopt hist_ignore_all_dups ;;
  findnodups) setopt hist_find_no_dups ;;
  prefix) HISTORY_SUBSTRING_SEARCH_PREFIXED=1 ;;
  case-sensitive) HISTORY_SUBSTRING_SEARCH_GLOBBING_FLAGS='' ;;
  nohighlight) WSH_DISABLE_SYNTAX_HIGHLIGHTING=1 ;;
esac""")
    harness = harness.replace("_capture() {", '''zle() {
  if [[ $1 == -R ]]; then captured_regions=("${region_highlight[@]}"); fi
  builtin zle "$@"
}
_capture() {''')
    harness = harness.replace('"$BUFFER"$\'\\x1f\'', '"$BUFFER|cursor=$CURSOR|regions=${(j:;:)captured_regions}"$\'\\x1f\'')
    harness = harness.replace("b'\\x10\\x0e']", "b'\\x10\\x0e',b'echo \\xc3\\xa9\\x10',b'echo duplicate\\x10\\x01\\x10',b'echo duplicate\\x10\\x0e\\x0e']")
    harness = harness.replace('PASS: 32 paired actual ZLE navigation, custom-widget and multiline cases', 'PASS: 110 paired ZLE buffer, cursor, highlight, Unicode, options and composition cases')
(out / 'harness.py').write_text(harness)
subprocess.run([sys.executable, out / 'harness.py', binary, module, out, out / 'results', mode], check=True)
