#!/usr/bin/env python3
"""Replace only position accounting in private copies of the upstream fixture."""
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
        start = source.index('      # Compute the new $start_pos and $end_pos')
        end = source.index('\n    fi', start)
        source = source[:start] + '      builtin wsh-highlight-position' + source[end:]
        path.write_text('module_path=(' + shlex.quote(str(module)) + ' $module_path)\nzmodload wshhighlighttraversal || return 2\n' + source)
