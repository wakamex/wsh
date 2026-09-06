#!/usr/bin/env python3
"""Run the fixed six-run comparison without concurrent validation work."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
builds = json.loads((OUT / 'builds.json').read_text())
env = {k: v for k, v in os.environ.items() if not k.startswith('WSH_')}
env['WSH_PROFILE_CPU'] = '0'
manager = ROOT / 'target/release/wsh'
assert hashlib.sha256(manager.read_bytes()).hexdigest() == builds['baseline']['manager_sha256']
results = []
for index, name in enumerate(['baseline', 'modules', 'both', 'both', 'modules', 'baseline'], 1):
    prefix = OUT / f'{index}-{name}'
    before = {'at': time.time(), 'loadavg': Path('/proc/loadavg').read_text(),
              'stat': Path('/proc/stat').read_text(),
              'observer_affinity': sorted(os.sched_getaffinity(0))}
    command = [str(ROOT / 'benchmarks/benchmark-profile.zsh'), str(prefix) + '-samples.tsv',
               str(manager), builds[name]['bundle'], '50']
    with Path(str(prefix) + '-benchmark.log').open('w') as log:
        subprocess.run(command, cwd=ROOT, env=env, check=True, stdout=log, stderr=subprocess.STDOUT)
    after = {'at': time.time(), 'loadavg': Path('/proc/loadavg').read_text(),
             'stat': Path('/proc/stat').read_text()}
    Path(str(prefix) + '-host.json').write_text(json.dumps({'before': before, 'after': after}, indent=2) + '\n')
    subprocess.run([str(ROOT / 'benchmarks/summarize-profile.zsh'), str(prefix) + '-samples.tsv',
                    str(prefix) + '-summary.tsv'], check=True, stdout=subprocess.DEVNULL)
    with Path(str(prefix) + '-gates.tsv').open('w') as gates:
        result = subprocess.run([str(ROOT / 'benchmarks/check-profile-gates.zsh'),
                                 str(prefix) + '-summary.tsv',
                                 str(ROOT / 'benchmarks/profile-2026-09-05/runtime-trace.tsv')], stdout=gates)
    assert result.returncode in (0, 1)
    gate = Path(str(prefix) + '-gates.tsv').read_text().splitlines()[1]
    print(index, name, gate, flush=True)
    results.append({'index': index, 'variant': name, 'command': command, 'gate': gate})
(OUT / 'runs.json').write_text(json.dumps(results, indent=2) + '\n')
