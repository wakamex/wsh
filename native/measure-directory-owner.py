#!/usr/bin/env python3
"""Paired complete command costs on correctness-checked ordinary directory records."""
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

binary, module, fixture, out = [Path(p).resolve() for p in sys.argv[1:5]]
checking = len(sys.argv) > 5 and sys.argv[5] == 'correctness'
out.mkdir(parents=True, exist_ok=True)
home = out / 'home'
home.mkdir(exist_ok=True)
script = out / 'run.zsh'
script.write_text('''module_path=($1 $module_path)
(( $+builtins[wsh-directory] )) || zmodload wshdirectory || exit 90
source "$2"
shift 2
zshz "$@"
''')
env = dict(PATH='/usr/bin:/bin', HOME=str(home), ZSHZ_DATA=str(home/'db'), WSH_QUERY_NOW='1800000000', LC_ALL='C.UTF-8')
env.update({k: v for k, v in os.environ.items() if k.endswith('SAN_OPTIONS')})
os.sched_setaffinity(0, {0})
summary = {}
for count in (100, 1000):
    paths = [home / ('needle' if i == count-1 else f'project-{i}') for i in range(count)]
    for path in paths:
        path.mkdir(exist_ok=True)
    data = ''.join(str(path)+'|2|1700000000\n' for path in paths)
    for operation in ('lookup', 'write'):
        args = ['-e', 'needle'] if operation == 'lookup' else ['--add', str(paths[-1])]
        pairs = []
        for i in range(1 if checking else 50):
            pair = {}
            results = {}
            for owner in ('control', 'candidate') if i % 2 == 0 else ('candidate', 'control'):
                (home/'db').write_text(data)
                start = time.perf_counter_ns()
                run = subprocess.run([binary, '-df', script, module, fixture/(owner+'.zsh'), *args], env=env, capture_output=True, timeout=10)
                pair[owner] = (time.perf_counter_ns()-start)/1e6
                assert run.returncode == 0 and not run.stderr, run
                result = (run.stdout, (home/'db').read_bytes())
                results[owner] = result
            assert results['control'] == results['candidate'], (count, operation, results)
            pairs.append(pair)
        medians = {owner: statistics.median(p[owner] for p in pairs) for owner in ('control','candidate')}
        summary[f'{count}/{operation}'] = dict(pairs=pairs, median_ms=medians, paired_p95_delta_ms=sorted(p['candidate']-p['control'] for p in pairs)[0 if checking else 47], median_reduction=1-medians['candidate']/medians['control'], fixture_sha256=hashlib.sha256(data.encode()).hexdigest())
(out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps({k:{n:v for n,v in r.items() if n!='pairs'} for k,r in summary.items()}, indent=2))
