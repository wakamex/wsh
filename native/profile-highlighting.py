#!/usr/bin/env python3
"""Attribute complete redraws with Zsh's profiler and quantify its own overhead."""
import json
import os
from pathlib import Path
import shlex
import statistics
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
binary,out=[Path(p).resolve() for p in sys.argv[1:]]
out.mkdir(parents=True,exist_ok=True)
script=out/'profile.zsh'
script.write_text(r'''source $1
zmodload zsh/datetime
typeset -a buffers samples
buffers=('echo hello')
repeated='' distinct=''
for ((i=1;i<=100;i++)); do
 functions[wsh_probe_$i]=':'
 repeated+='echo hello; '
 distinct+="wsh_probe_$i hello; "
done
buffers+=("$repeated" "$distinct" $'if true; then\n echo "${HOME}"\nfi')
CONTEXT=start PREBUFFER=''
for ((workload=1;workload<=4;workload++)); do
 BUFFER=$buffers[$workload] CURSOR=$#BUFFER
 for ((i=0;i<50;i++)); do
  modes=(off on)
  ((i%2)) && modes=(on off)
  for mode in $modes; do
   [[ $mode == on ]] && zmodload zsh/zprof
   _zsh_highlight_main__command_type_cache=()
   region_highlight=()
   start=$EPOCHREALTIME
   _zsh_highlight_highlighter_main_paint
   elapsed=$(( (EPOCHREALTIME-start)*1000 ))
   samples+=("$workload $i $mode $elapsed ${(qqq)${(j:|:)region_highlight}}")
   if [[ $mode == on ]]; then
    zprof > "$2/profile-$workload-$i.txt"
    zmodload -u zsh/zprof
   fi
  done
 done
done
print -rl -- $samples
''')
run=subprocess.run([binary,'-df',script,root/'third_party/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh',out],env=dict(PATH='/usr/bin:/bin',HOME=str(out),LC_ALL='C.UTF-8',TERM='xterm-256color'),capture_output=True,timeout=180,preexec_fn=lambda:os.sched_setaffinity(0,{0}))
(out/'stdout').write_bytes(run.stdout);(out/'stderr').write_bytes(run.stderr)
assert run.returncode==0 and not run.stderr,(run.returncode,run.stderr)
rows=[shlex.split(line) for line in run.stdout.decode().splitlines()]
assert len(rows)==400
summary={}
for workload in range(1,5):
 pairs=[{} for _ in range(50)];regions=[{} for _ in range(50)]
 for w,i,mode,ms,region in rows:
  if int(w)==workload:pairs[int(i)][mode]=float(ms);regions[int(i)][mode]=region
 assert all(r['off']==r['on'] and r['off'] for r in regions)
 medians={m:statistics.median(p[m] for p in pairs) for m in ('off','on')}
 attribution={}
 for i in range(50):
  text=(out/f'profile-{workload}-{i}.txt').read_text()
  for line in text.split('\n\n',1)[0].splitlines()[2:]:
   fields=line.split()
   if len(fields)==9 and fields[0].endswith(')'):
    attribution.setdefault(fields[-1],[]).append(dict(calls=int(fields[1]),inclusive_ms=float(fields[2]),self_ms=float(fields[5])))
 summary[str(workload)]=dict(pairs=pairs,median_ms=medians,paired_p95_overhead_ms=sorted(p['on']-p['off'] for p in pairs)[47],functions={name:{key:statistics.median(v[key] for v in values) for key in ('calls','inclusive_ms','self_ms')} for name,values in attribution.items()})
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:{n:v for n,v in s.items() if n!='pairs'} for k,s in summary.items()},indent=2))
