#!/usr/bin/env python3
"""Paired startup cost up to the first editable prompt for several Wsh installations and startup files.

Reports the shell's own CPU time, which stays comparable on a busy machine, alongside wall time.

Usage: measure.py OMZ OUTPUT ROUNDS NAME=WSH...
"""
import json
import os
from pathlib import Path
import pty
import select
import shlex
import signal
import statistics
import sys
import time

omz, output, rounds = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), int(sys.argv[3])
installations = dict(argument.split('=', 1) for argument in sys.argv[4:])
OMZ = f'ZSH={shlex.quote(str(omz))}\nZSH_THEME=""\nplugins=()\nzstyle ":omz:update" mode disabled\nsource "$ZSH/oh-my-zsh.sh"\n'
CONFIGS = {'empty': '', 'own-compinit': 'autoload -Uz compinit\ncompinit\n', 'omz': OMZ, 'no-completion': 'WSH_DISABLE_COMPLETION=1\n'}
READY = b'\x1b]133;B'


def start(wsh, home):
    env = dict(PATH='/usr/bin:/bin', HOME=str(home), ZDOTDIR=str(home), TERM='xterm-256color', LC_ALL='C.UTF-8', WSH_THEME='',
               LS_COLORS='di=01;34')
    began = time.perf_counter()
    pid, fd = pty.fork()
    if not pid:
        os.chdir(home)
        os.execve(wsh, ['wsh', '-di'], env)
    data = bytearray()
    while READY not in data:
        assert time.perf_counter() - began < 20, bytes(data[-500:])
        if select.select([fd], [], [], .05)[0]:
            data.extend(os.read(fd, 65536))
    elapsed = (time.perf_counter() - began) * 1000
    assert b'Wsh integration unavailable' not in data
    os.kill(pid, signal.SIGKILL)
    usage = os.wait4(pid, 0)[2]
    os.close(fd)
    return (usage.ru_utime + usage.ru_stime) * 1000, elapsed


cases = [(name, config) for name in installations for config in CONFIGS]
samples = {case: [] for case in cases}
for name, config in cases:
    home = output / name / config
    home.mkdir(parents=True, exist_ok=True)
    (home / '.zshrc').write_text(CONFIGS[config])
    for _ in range(3):  # Write the completion dump and warm the file cache.
        start(installations[name], home)
for _ in range(rounds):
    for name, config in cases:
        samples[name, config].append(start(installations[name], output / name / config))
rows = []
for (name, config), values in samples.items():
    cpu, wall = [sorted(value[i] for value in values) for i in (0, 1)]
    rows.append(dict(installation=name, startup_file=config, samples=len(values), cpu_median_ms=round(statistics.median(cpu), 3),
                     cpu_p95_ms=round(cpu[int(len(cpu) * .95) - 1], 3), wall_median_ms=round(statistics.median(wall), 3)))
    print(f"{name:10} {config:14} cpu median {rows[-1]['cpu_median_ms']:7.3f} ms  p95 {rows[-1]['cpu_p95_ms']:7.3f} ms  wall median {rows[-1]['wall_median_ms']:8.3f} ms")
(output / 'results.json').write_text(json.dumps(dict(rows=rows, samples={f'{n}/{c}': v for (n, c), v in samples.items()}), indent=2) + '\n')
