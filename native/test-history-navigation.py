#!/usr/bin/env python3
"""Compare matching and navigation with actual Zsh history and the pinned plugin."""
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys

binary, module, fixture, out = [Path(p).resolve() for p in sys.argv[1:]]
out.mkdir(parents=True, exist_ok=True)
script = out/'compare.zsh'
script.write_text('''module_path=($1 $module_path)
zmodload wshhistory || exit 2
source $2
zmodload zsh/parameter
fc -p
HISTSIZE=1000
unsetopt hist_ignore_all_dups hist_ignore_dups hist_find_no_dups
for text in 'echo older' 'echo older' 'echo newer' $'echo multiline\\nnext' 'Echo MIXED' 'echo [x]' 'echo *star' 'echo é' 'other' 'sentinel'; do print -s -- "$text"; done
HISTORY_SUBSTRING_SEARCH_ENSURE_UNIQUE=$3
HISTORY_SUBSTRING_SEARCH_FUZZY=$4
HISTORY_SUBSTRING_SEARCH_PREFIXED=$5
(( $6 )) && setopt hist_find_no_dups
HISTORY_SUBSTRING_SEARCH_GLOBBING_FLAGS=$7
for query in 'echo' 'echo older' 'echo new' '[x]' '*star' 'é' 'absent'; do
 BUFFER=$query
 _history_substring_search_result=''
 for direction in up up up down up up up up up up down down down down down; do
  WIDGET=history-substring-search-$direction
  _history-substring-search-begin
  _history-substring-search-$direction-search
  print -r -- "${(qqqq)BUFFER}:$_history_substring_search_match_index:${(qqqq)_history_substring_search_query_highlight}"
  _history_substring_search_result=$BUFFER
 done
 print -s -- 'echo live history'
 print -s -- 'sentinel'
done
''')
rows = []
for unique, fuzzy, prefixed, nodups, flags in itertools.product(('', '1'), ('', '1'), ('', '1'), ('0', '1'), ('i', '')):
    variants = []
    for owner in ('control', 'candidate'):
        run = subprocess.run([binary, '-df', script, module, fixture/f'{owner}.zsh', unique, fuzzy, prefixed, nodups, flags], env=dict(os.environ, HOME=str(out), LC_ALL='C.UTF-8'), capture_output=True, timeout=10)
        variants.append(dict(status=run.returncode, stdout=run.stdout.hex(), stderr=run.stderr.hex()))
    row = dict(config=[unique,fuzzy,prefixed,nodups,flags], variants=variants, equal=variants[0] == variants[1])
    rows.append(row)
    if not row['equal'] or any(v['stderr'] or v['status'] for v in variants): break
(out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
assert all(r['equal'] and all(v['status']==0 and not v['stderr'] for v in r['variants']) for r in rows), rows[-1]['config']
print(f'PASS: {len(rows)*105} navigation transitions across {len(rows)} configurations')
