#!/usr/bin/env python3
"""Compare the reference, native quote flag and C history selection strategy."""
import json
import os
from pathlib import Path
import random
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
binary, module, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
upstream = (root / 'third_party/zsh-autosuggestions/zsh-autosuggestions.zsh').read_text()
line = next(line for line in upstream.splitlines() if 'local prefix=' in line)
candidate = upstream.replace(line, '\tlocal prefix="${(b)1}"')
(output / 'builtin.zsh').write_text(candidate)
rng = random.Random(90509)
prefixes = ['', 'echo', 'missing', 'echo space ', 'écho', 'echo\n', 'echo $(false)', 'echo [x]', 'echo \\']
prefixes += ['echo ' + ''.join(rng.choices('abc *?[]<>|^~#\\()é\t', k=rng.randrange(1, 40))) for _ in range(1000)]
def quote(text):
    return "'" + text.replace("'", "'\\''") + "'"
(output / 'prefixes.zsh').write_text('prefixes=(' + ' '.join(map(quote, prefixes)) + ')\n')
script = output / 'compare.zsh'
script.write_text('''module_path=($1 $module_path)
zmodload wshsuggest || exit 2
source $2
zmodload zsh/parameter
fc -p
HISTSIZE=10000
unsetopt hist_ignore_all_dups hist_ignore_dups
source $3
for prefix in $prefixes; do print -s -- "$prefix suffix"; done
print -s -- 'sentinel'
[[ $4 == candidate ]] && functions[_zsh_autosuggest_strategy_history]='emulate -L zsh; setopt extended_glob; wsh-history-suggest "$1"'
for ignore in '' '*suffix' '*[ab]*' '(#i)*ECHO*' '[' '('; do
 ZSH_AUTOSUGGEST_HISTORY_IGNORE=$ignore
 for prefix in "${prefixes[@]}"; do
  _zsh_autosuggest_strategy_history "$prefix"
  result=$?
  print -r -- "$result ${(qqqq)suggestion}"
 done
 print -s -- 'echo new history'
 print -s -- 'sentinel next'
done
''')
rows = []
for owner in ('control', 'builtin', 'candidate'):
    source = output / 'builtin.zsh' if owner == 'builtin' else root / 'third_party/zsh-autosuggestions/zsh-autosuggestions.zsh'
    run = subprocess.run([binary, '-df', script, module, source, output / 'prefixes.zsh', owner],
                         env=dict(os.environ, HOME=str(output), LC_ALL='C.UTF-8'), capture_output=True, timeout=120)
    (output / f'{owner}.stdout').write_bytes(run.stdout)
    (output / f'{owner}.stderr').write_bytes(run.stderr)
    rows.append(dict(owner=owner, status=run.returncode, stdout=run.stdout.hex(), stderr=run.stderr.hex()))
(output / 'results.json').write_text(json.dumps(rows, indent=2) + '\n')
assert all(r['status'] == 0 and not r['stderr'] for r in rows)
assert len({r['stdout'] for r in rows}) == 1, 'suggestion parity failed; inspect retained outputs'
print(f'PASS: {len(prefixes) * 6} suggestions match across reference, builtin and C strategies')
