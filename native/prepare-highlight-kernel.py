#!/usr/bin/env python3
"""Keep the upstream suite and highlighter intact around a classifier replacement."""
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[1]
upstream, module, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
for owner in ('control', 'candidate'):
    target = output / owner
    shutil.copytree(upstream, target, ignore=shutil.ignore_patterns('.git'))
    # Use the exact shipped sources with the upstream test corpus.
    shutil.copytree(root / 'third_party/zsh-syntax-highlighting', target, dirs_exist_ok=True)
    main = target / 'highlighters/main/main-highlighter.zsh'
    if owner == 'candidate':
        source = main.read_text()
        start = source.index('    if (( $+aliases[(e)$1] )); then')
        end = source.index('    # None of the special hashes', start)
        source = source[:start] + '    if wsh-highlight-type "$1" "$aliases_allowed"; then\n      :\n' + source[end:]
        # Modules are loaded only in this private fixture.
        main.write_text('module_path=(' + str(module) + ' $module_path)\nzmodload wshhighlight || return 2\n' + source)
