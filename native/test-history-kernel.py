#!/usr/bin/env python3
"""Exercise the real plugin and C lazy filter against actual Zsh history."""
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
binary, module, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
script = output / 'compare.zsh'
script.write_text('''module_path=($1 $module_path)
zmodload wshhistory || exit 2
source $2
zmodload zsh/parameter
fc -p
HISTSIZE=20000
unsetopt hist_ignore_all_dups hist_ignore_dups
for ((i=0;i<100;i++)); do
 print -s -- "echo project $((i%7))"
done
print -s -- $'echo multiline\\nsecond line'
print -s -- 'echo $(false) [x] `false` ; quote'
print -s -- 'sentinel current event'
(( $4 )) && setopt hist_ignore_all_dups
HISTORY_SUBSTRING_SEARCH_ENSURE_UNIQUE=$5
_history_substring_search_raw_matches=(${(Onk)history})
_history_substring_search_raw_match_index=0
_history_substring_search_matches=()
_history_substring_search_unique_filter=()
_history_substring_search_unique_filter['echo project 0']=''
[[ $3 == candidate ]] && functions[_history_substring_search_process_raw_matches]='wsh-history-next'
for ((i=0;i<110;i++)); do
 _history_substring_search_process_raw_matches
 result=$?
 print -r -- "$result $_history_substring_search_raw_match_index ${(j:,:) _history_substring_search_matches}"
 # New history between calls must not change the already selected raw indices.
 ((i==3)) && print -s -- 'echo later history'
done
print -rl -- ${(ok)_history_substring_search_unique_filter}
'''.replace('${(j:,:) _history', '${(j:,:)_history'))
rows = []
for ignore in ('0', '1'):
    for unique in ('', '1'):
        variants = []
        for owner in ('control', 'candidate'):
            run = subprocess.run([binary, '-df', script, module,
                                  root / 'third_party/zsh-history-substring-search/zsh-history-substring-search.zsh',
                                  owner, ignore, unique], env=dict(os.environ, HOME=str(output), LC_ALL='C.UTF-8'),
                                 capture_output=True, timeout=10)
            (output / f'{owner}-{ignore}-{unique}.stdout').write_bytes(run.stdout)
            (output / f'{owner}-{ignore}-{unique}.stderr').write_bytes(run.stderr)
            variants.append(dict(status=run.returncode, stdout=run.stdout.hex(), stderr=run.stderr.hex()))
        rows.append(dict(ignore=ignore, unique=unique, results=variants, equal=variants[0] == variants[1]))
(output / 'results.json').write_text(json.dumps(rows, indent=2) + '\n')
assert all(r['equal'] and all(v['status'] == 0 and not v['stderr'] for v in r['results']) for r in rows), rows
print('PASS: four history modes, 440 lazy transitions, live history and exact state parity')
