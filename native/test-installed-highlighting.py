#!/usr/bin/env python3
"""Exercise the installed native main adapter against its pinned original source."""
from pathlib import Path
import shutil
import subprocess
import sys
root = Path(__file__).resolve().parents[1]
installation, out = map(lambda s: Path(s).resolve(), sys.argv[1:])
fixture = out / 'fixture'
source = installation / 'share/wsh/defaults/zsh-syntax-highlighting'
for owner in ('control', 'candidate'):
    target = fixture / owner
    shutil.copytree(source, target)
    main = target / 'highlighters/main/main-highlighter.zsh'
    main.with_suffix('.zsh.zwc').unlink(missing_ok=True)
    if owner == 'control':
        shutil.copy2(main.with_name('known-main-highlighter.zsh'), main)
    else:
        text = main.read_text()
        assert 'builtin wsh-highlight-main' in text
        assert '_zsh_highlight_main_highlighter_highlight_list' not in text
binary = installation / 'bin/wsh'
for command in (
    ['native/test-highlight-full-differential.py', binary, fixture, out / 'prefixes'],
    ['native/test-highlight-traversal-zle.py', binary, fixture, out / 'editor', 'correctness'],
    ['native/test-highlight-full-lifetime.py', binary, fixture / 'candidate/zsh-syntax-highlighting.zsh', out / 'lifetime'],
):
    subprocess.run([sys.executable, root / command[0], *command[1:]], check=True)
print('PASS: installed native main ownership, exact styles, composed editor and bounded lifetime')
