#!/usr/bin/env python3
"""Alternating, fixed-clock lookup comparisons, with no output in timed spans."""
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

binary, module, prototype, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
summary = {}
for count in (100, 1000):
    home = output / str(count)
    home.mkdir(exist_ok=True)
    entries = []
    for i in range(count):
        directory = home / f"project-{i:04}"
        directory.mkdir(exist_ok=True)
        entries.append(f"{directory}|{i % 30 + 1}|1700000000\n")
    (home / "db").write_text("".join(entries))
    script = home / "measure.zsh"
    script.write_text('''module_path=($1 $module_path)
zmodload wshdirectory || exit 2
zmodload zsh/datetime
control=$2/control.zsh candidate=$2/candidate.zsh
source $control
zshz -e project >/dev/null
source $candidate
zshz -e project >/dev/null
typeset -a rows
for ((i=0;i<50;i++)); do
 owners=(control candidate)
 ((i % 2)) && owners=(candidate control)
 for owner in $owners; do
  source ${(P)owner}
  start=$EPOCHREALTIME
  zshz -e project >/dev/null
  elapsed=$(( (EPOCHREALTIME-start)*1000 ))
  rows+=("$i $owner $elapsed")
 done
done
print -rl -- $rows
''')
    run = subprocess.run([binary, "-df", script, module, prototype], capture_output=True,
                         env=dict(PATH="/usr/bin:/bin", HOME=str(home),
                                  ZSHZ_DATA=str(home / "db"), WSH_QUERY_NOW="1800000000", LC_ALL="C.UTF-8"),
                         timeout=120, preexec_fn=lambda: os.sched_setaffinity(0, {0}))
    (home / "stdout").write_bytes(run.stdout)
    (home / "stderr").write_bytes(run.stderr)
    assert run.returncode == 0 and not run.stderr
    rows = [line.split() for line in run.stdout.decode().splitlines()]
    assert len(rows) == 100
    pairs = [{} for _ in range(50)]
    for index, owner, ms in rows:
        pairs[int(index)][owner] = float(ms)
    medians = {owner: statistics.median(p[owner] for p in pairs) for owner in ("control", "candidate")}
    delta = sorted(p["candidate"] - p["control"] for p in pairs)[47]
    summary[count] = dict(pairs=pairs, median_ms=medians, paired_p95_delta_ms=delta,
                          median_reduction=1 - medians["candidate"] / medians["control"])
(output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({n: {k: v for k, v in s.items() if k != "pairs"} for n, s in summary.items()}, indent=2))
