#!/usr/bin/env python3
"""Compare complete main-highlighter calls with cold and reusable command caches."""
import json
import os
from pathlib import Path
import shlex
import statistics
import subprocess
import sys

binary, fixture, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
script = output / 'measure.zsh'
script.write_text('''source $1/control/zsh-syntax-highlighting.zsh
functions[control_type]=$functions[_zsh_highlight_main__type]
source $1/candidate/highlighters/main/main-highlighter.zsh
functions[candidate_type]=$functions[_zsh_highlight_main__type]
zmodload zsh/datetime
typeset -a samples buffers
buffers=('echo hello')
repeated='' distinct=''
for ((i=1;i<=100;i++)); do
 functions[wsh_probe_$i]=':'
 repeated+='echo hello; '
 distinct+="wsh_probe_$i hello; "
done
buffers+=("$repeated" "$distinct" $'if true; then\\n echo "${HOME}"\\nfi')
CONTEXT=start PREBUFFER=''
for ((workload=1;workload<=4;workload++)); do
 BUFFER=$buffers[$workload] CURSOR=$#BUFFER
 for cache in cold warm; do
  for ((i=0;i<50;i++)); do
   owners=(control candidate)
   ((i%2)) && owners=(candidate control)
   for owner in $owners; do
    functions[_zsh_highlight_main__type]=$functions[${owner}_type]
    _zsh_highlight_main__command_type_cache=()
    region_highlight=()
    [[ $cache == warm ]] && _zsh_highlight_highlighter_main_paint
    region_highlight=()
    start=$EPOCHREALTIME
    _zsh_highlight_highlighter_main_paint
    elapsed=$(( (EPOCHREALTIME-start)*1000 ))
    spans=${(j:|:)region_highlight}
    samples+=("$workload $cache $i $owner $elapsed ${(qqq)spans}")
   done
  done
 done
done
print -rl -- $samples
''')
run = subprocess.run([binary, '-df', script, fixture],
                     env=dict(PATH='/usr/bin:/bin', HOME=str(output), LC_ALL='C.UTF-8', TERM='xterm-256color'),
                     capture_output=True, timeout=180, preexec_fn=lambda: os.sched_setaffinity(0, {0}))
(output / 'stdout').write_bytes(run.stdout)
(output / 'stderr').write_bytes(run.stderr)
assert run.returncode == 0 and not run.stderr
rows = [shlex.split(line) for line in run.stdout.decode().splitlines()]
assert len(rows) == 800
summary = {}
for workload in range(1, 5):
    for cache in ('cold', 'warm'):
        pairs = [{} for _ in range(50)]
        spans = {}
        for w, c, index, owner, ms, result in rows:
            if int(w) == workload and c == cache:
                pairs[int(index)][owner] = float(ms)
                spans.setdefault(index, {})[owner] = result
        assert all(v['control'] == v['candidate'] and v['control'] for v in spans.values())
        medians = {owner: statistics.median(p[owner] for p in pairs) for owner in ('control', 'candidate')}
        summary[f'{workload}/{cache}'] = dict(pairs=pairs, median_ms=medians,
            paired_p95_delta_ms=sorted(p['candidate'] - p['control'] for p in pairs)[47],
            median_reduction=1 - medians['candidate'] / medians['control'])
(output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({n: {k: v for k, v in s.items() if k != 'pairs'} for n, s in summary.items()}, indent=2))
