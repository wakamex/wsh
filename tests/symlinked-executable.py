#!/usr/bin/env python3
"""Check that Wsh started through a symlink, as Homebrew installs it, finds its resources.

Usage: symlinked-executable.py WSH OUTPUT
"""
import os
from pathlib import Path
import subprocess
import sys

wsh = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
(output / 'bin').mkdir(parents=True, exist_ok=True)
link = output / 'bin' / 'wsh'
link.unlink(missing_ok=True)
link.symlink_to(wsh)
env = dict(PATH='/usr/bin:/bin', HOME=str(output), ZDOTDIR=str(output), TERM='dumb', LC_ALL='C.UTF-8')
result = subprocess.run([link, '-ic', 'print -r -- "$WSH_BUNDLE_ROOT|${+functions[compdef]}"'], env=env, capture_output=True, text=True, timeout=30)
root, _, completion = result.stdout.strip().rpartition('\n')[2].partition('|')
assert 'integration unavailable' not in result.stderr, result.stderr
assert root == str(wsh.parent.parent), (root, result.stderr)
assert completion == '1', (result.stdout, result.stderr)
print('PASS: Wsh started through a symlink finds its resources and interactive defaults')
