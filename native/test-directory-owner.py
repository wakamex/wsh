#!/usr/bin/env python3
"""Falsify complete directory ownership against the actual pinned implementation."""
import json
import os
from pathlib import Path
import subprocess
import sys

binary, module, fixture, out = [Path(p).resolve() for p in sys.argv[1:]]
out.mkdir(parents=True, exist_ok=True)
home = out / 'home'
home.mkdir(exist_ok=True)
for name in ('project', 'other', 'tab\tpath', 'pipe|path'):
    (home / name).mkdir(exist_ok=True)
script = out / 'compare.zsh'
script.write_text('''module_path=($1 $module_path)
zmodload wshdirectory || exit 90
source $2
shift 2
local_setup=$1
shift
 eval "$local_setup"
zshz "$@"
result=$?
print -r -- "STATUS:$result"
''')
base = f'{home}/project|2|1700000000\n{home}/other|3|1700000010\n'
cases = [
    ('add', base, '', ['--add', str(home/'project')]),
    ('age', base, 'ZSHZ_MAX_SCORE=1', ['--add', str(home/'project')]),
    ('remove', base, '', ['-x', str(home/'project')]),
    ('missing-remove', base, '', ['-x', str(home/'absent')]),
    ('duplicate', base + f'{home}/project|7|1700000001\n', '', ['--add', str(home/'project')]),
    ('excluded', base, 'ZSHZ_EXCLUDE_DIRS=($HOME/project)', ['--add', str(home/'project')]),
    ('home-relative', base, 'cd $HOME', ['--add', '.']),
    ('legacy-completion', base, 'ZSHZ_COMPLETION=legacy', ['--complete', 'project']),
    ('pipe', base, '', ['--add', str(home/'pipe|path')]),
    ('tab', base, '', ['--add', str(home/'tab\tpath')]),
]
rows = []
for name, data, setup, args in cases:
    variants = []
    for owner in ('control', 'candidate'):
        (home/'db').write_text(data)
        run = subprocess.run([binary, '-df', script, module, fixture/f'{owner}.zsh', setup, *args],
            env=dict(os.environ, HOME=str(home), ZSHZ_DATA=str(home/'db'), WSH_QUERY_NOW='1800000000', LC_ALL='C.UTF-8'),
            capture_output=True, timeout=5)
        variants.append(dict(status=run.returncode, stdout=run.stdout.hex(), stderr=run.stderr.hex(), database=(home/'db').read_bytes().hex()))
    rows.append(dict(name=name, variants=variants, exact_equal=variants[0] == variants[1]))
(out/'results.json').write_text(json.dumps(rows, indent=2)+'\n')
assert all(v['status'] == 0 and not v['stderr'] for row in rows for v in row['variants']), rows
print(json.dumps({row['name']: row['exact_equal'] for row in rows}, indent=2))
assert all(row['exact_equal'] for row in rows if row['name'] != 'tab'), rows
