#!/usr/bin/env python3
"""Measure the same duplicate run through the lazy reference and C filter."""
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
binary, module, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
script = output / 'measure.zsh'
script.write_text('''module_path=($1 $module_path)
zmodload wshhistory || exit 2
zmodload zsh/datetime
source $2
zmodload zsh/parameter
fc -p
HISTSIZE=20000
unsetopt hist_ignore_all_dups hist_ignore_dups
repeat $3; do print -s -- 'echo duplicate'; done
print -s -- 'sentinel'
HISTORY_SUBSTRING_SEARCH_ENSURE_UNIQUE=1
typeset -a rows
typeset -a fixture=(${(Onk)history})
[[ $#fixture == $3 ]] || exit 4
for ((i=0;i<50;i++)); do
 owners=(control candidate)
 ((i%2)) && owners=(candidate control)
 for owner in $owners; do
  _history_substring_search_raw_matches=($fixture)
  _history_substring_search_raw_match_index=0
  _history_substring_search_matches=()
  _history_substring_search_unique_filter=()
  _history_substring_search_process_raw_matches
  start=$EPOCHREALTIME
  if [[ $owner == control ]]; then
   _history_substring_search_process_raw_matches
  else
   wsh-history-next
  fi
  result=$?
  elapsed=$(( (EPOCHREALTIME-start)*1000 ))
  [[ $result == 1 && $_history_substring_search_raw_match_index == $3 ]] || exit 3
  rows+=("$i $owner $elapsed")
 done
done
print -rl -- $rows
''')
summary = {}
for count in (100, 10000):
    run = subprocess.run([binary, '-df', script, module,
                          root / 'third_party/zsh-history-substring-search/zsh-history-substring-search.zsh', str(count)],
                         env=dict(PATH='/usr/bin:/bin', HOME=str(output), LC_ALL='C.UTF-8'),
                         capture_output=True, timeout=120, preexec_fn=lambda: os.sched_setaffinity(0, {0}))
    (output / f'{count}.stdout').write_bytes(run.stdout)
    (output / f'{count}.stderr').write_bytes(run.stderr)
    assert run.returncode == 0 and not run.stderr
    rows = [line.split() for line in run.stdout.decode().splitlines()]
    assert len(rows) == 100
    pairs = [{} for _ in range(50)]
    for index, owner, ms in rows:
        pairs[int(index)][owner] = float(ms)
    medians = {owner: statistics.median(p[owner] for p in pairs) for owner in ('control', 'candidate')}
    summary[count] = dict(pairs=pairs, median_ms=medians,
                          paired_p95_delta_ms=sorted(p['candidate'] - p['control'] for p in pairs)[47],
                          median_reduction=1 - medians['candidate'] / medians['control'])
(output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({n: {k: v for k, v in s.items() if k != 'pairs'} for n, s in summary.items()}, indent=2))
