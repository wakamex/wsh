#!/usr/bin/env python3
"""Alternating reference, builtin-only and C history strategy timings."""
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
binary, module, fixture, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
script = output / 'measure.zsh'
script.write_text('''module_path=($1 $module_path)
zmodload wshsuggest || exit 2
zmodload zsh/datetime
source $2
functions[control]=$functions[_zsh_autosuggest_strategy_history]
source $3
functions[quote_builtin]=$functions[_zsh_autosuggest_strategy_history]
candidate() { emulate -L zsh; setopt extended_glob; wsh-history-suggest "$1"; }
zmodload zsh/parameter
fc -p
HISTSIZE=20000
for ((i=0;i<$4;i++)); do print -s -- "echo project $i"; done
print -s -- sentinel
typeset -a rows
for query in 'echo project' 'no-match'; do
 control "$query"; quote_builtin "$query"; candidate "$query"
 for ((i=0;i<50;i++)); do
  owners=(control quote_builtin candidate)
  ((i%2)) && owners=(candidate quote_builtin control)
  for owner in $owners; do
   start=$EPOCHREALTIME
   $owner "$query"
   elapsed=$(( (EPOCHREALTIME-start)*1000 ))
   rows+=("$i ${(qqq)query} $owner $elapsed ${(qqq)suggestion}")
  done
 done
done
print -rl -- $rows
''')
summary = {}
import shlex
for count in (100, 10000):
    run = subprocess.run([binary, '-df', script, module,
                          root / 'third_party/zsh-autosuggestions/zsh-autosuggestions.zsh', fixture / 'builtin.zsh', str(count)],
                         env=dict(PATH='/usr/bin:/bin', HOME=str(output), LC_ALL='C.UTF-8'),
                         capture_output=True, timeout=120, preexec_fn=lambda: os.sched_setaffinity(0, {0}))
    (output / f'{count}.stdout').write_bytes(run.stdout)
    (output / f'{count}.stderr').write_bytes(run.stderr)
    assert run.returncode == 0 and not run.stderr
    rows = [shlex.split(line) for line in run.stdout.decode().splitlines()]
    assert len(rows) == 300
    for query in ('echo project', 'no-match'):
        pairs = [{} for _ in range(50)]
        for index, q, owner, elapsed, suggestion in rows:
            if q != query:
                continue
            assert suggestion == (f'echo project {count - 1}' if query == 'echo project' else '')
            pairs[int(index)][owner] = float(elapsed)
        medians = {owner: statistics.median(p[owner] for p in pairs) for owner in ('control', 'quote_builtin', 'candidate')}
        summary[f'{count}/{query}'] = dict(pairs=pairs, median_ms=medians,
            paired_p95_delta_ms={owner: sorted(p[owner] - p['control'] for p in pairs)[47] for owner in ('quote_builtin', 'candidate')},
            c_reduction_from_builtin=1 - medians['candidate'] / medians['quote_builtin'])
(output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({n: {k: v for k, v in s.items() if k != 'pairs'} for n, s in summary.items()}, indent=2))
