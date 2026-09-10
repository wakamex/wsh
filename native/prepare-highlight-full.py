#!/usr/bin/env python3
"""Create authoritative fixtures with no old main parser in the C candidate."""
from pathlib import Path
import shlex
import shutil
import sys
root = Path(__file__).resolve().parents[1]
upstream, module, output = map(Path, sys.argv[1:])
for owner in ('control', 'candidate'):
    target = output / owner
    shutil.copytree(upstream, target, ignore=shutil.ignore_patterns('.git'))
    shutil.copytree(root / 'third_party/zsh-syntax-highlighting', target, dirs_exist_ok=True)
    if owner == 'candidate':
        path = target / 'highlighters/main/main-highlighter.zsh'
        source = path.read_text()
        source = source[:source.index('# Helper to deal with tokens crossing line boundaries.')]
        source += '\n_zsh_highlight_highlighter_main_paint() { builtin wsh-highlight-main }\n'
        source += 'typeset -ga ZSH_HIGHLIGHT_DIRS_BLACKLIST\n'
        path.write_text('module_path=(' + shlex.quote(str(module)) + ' $module_path)\nzmodload wshhighlightfull || return 2\n' + source)
        driver = target / 'tests/test-highlighting.zsh'
        test = driver.read_text()
        marker = '# Activate the highlighter.'
        test = test.replace(marker, """_zsh_highlight_highlighter_main_paint() {
  builtin wsh-highlight-main --symbolic
  local -a native_regions=("${region_highlight[@]}") fields
  local region
  region_highlight=()
  for region in "${native_regions[@]}"; do
    fields=( ${(s: :)region} )
    _zsh_highlight_add_highlight $fields[1] $fields[2] ${(s:,:)fields[3]}
  done
}

""" + marker)
        driver.write_text(test)
