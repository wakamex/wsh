#!/usr/bin/env python3
"""Compare aggregate steady prompt PSS for the shell and its per-session helper."""
import json
import os
from pathlib import Path
import pty
import select
import signal
import statistics
import sys
import tempfile
import time

control, candidate, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
rows = []
with tempfile.TemporaryDirectory(prefix='wsh-linked-memory-') as name:
    home = Path(name)
    (home / '.zshenv').write_text('unsetopt globalrcs\n')
    (home / '.zshrc').write_text('ZSHZ_DATA=$HOME/jump-data\n')
    for pair in range(20):
        order = ('control', 'candidate') if pair % 2 == 0 else ('candidate', 'control')
        for owner in order:
            bundle = control if owner == 'control' else candidate
            pid, fd = pty.fork()
            if not pid:
                os.sched_setaffinity(0, {0})
                os.chdir(home)
                os.execve(bundle / 'bin/wsh', [str(bundle / 'bin/wsh'), '-di'],
                          dict(PATH='/usr/bin:/bin', HOME=name, ZDOTDIR=name, WSH_THEME='minimal',
                               TERM='xterm-256color', LC_ALL='C.UTF-8'))
            try:
                transcript = bytearray()
                deadline = time.monotonic() + 8
                while b'\x1b]133;B\x1b\\' not in transcript:
                    assert time.monotonic() < deadline
                    if select.select([fd], [], [], .05)[0]:
                        transcript.extend(os.read(fd, 65536))
                # Collect after initial asynchronous work, at the same fixed boundary.
                time.sleep(.1)
                children = Path(f'/proc/{pid}/task/{pid}/children').read_text().split()
                assert len(children) == 1, children
                processes = []
                for process in [str(pid), *children]:
                    raw = Path(f'/proc/{process}/smaps_rollup').read_text()
                    pss = int(next(line for line in raw.splitlines() if line.startswith('Pss:')).split()[1])
                    processes.append(dict(pid=int(process), pss_kib=pss, smaps_rollup=raw))
                rows.append(dict(pair=pair, owner=owner, processes=processes,
                                 pss_kib=sum(p['pss_kib'] for p in processes)))
            finally:
                try:
                    os.killpg(pid, signal.SIGHUP)
                except ProcessLookupError:
                    pass
                os.close(fd)
                os.waitpid(pid, 0)
pairs = [{r['owner']: r['pss_kib'] for r in rows if r['pair'] == i} for i in range(20)]
differences = [p['candidate'] - p['control'] for p in pairs]
summary = dict(median_kib={owner: statistics.median(p[owner] for p in pairs) for owner in ('control', 'candidate')},
               max_delta_kib=max(differences), p95_delta_kib=sorted(differences)[18], limit_kib=4096)
summary['passed'] = summary['max_delta_kib'] <= summary['limit_kib']
(output / 'samples.json').write_text(json.dumps(rows, indent=2) + '\n')
(output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
