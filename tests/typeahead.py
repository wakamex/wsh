#!/usr/bin/env python3
"""Check that keys typed before the shell is ready are not lost.

Usage: typeahead.py OUTPUT SHELL [SHELL...]

Each SHELL starts interactive without startup files in a pseudo-terminal. The test types
several command lines at once, both at the prompt and while a command is still running,
and requires every line to run in order. Passing several shells, such as Wsh, the
reference Zsh and the system Zsh, shows which one loses input.
"""
import os
from pathlib import Path
import re
import pty
import select
import signal
import sys
import time

output = Path(sys.argv[1]).resolve()
output.mkdir(parents=True, exist_ok=True)
shells = [Path(p).absolute() for p in sys.argv[2:]]
failures = []
# OSC sequences end with BEL or ST; CSI sequences with a final letter.
ESCAPES = re.compile(rb'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;?>=]*[A-Za-z]|\x1bP[^\x1b]*\x1b\\')


def read_until(fd, data, marker, seconds=15):
    end = time.monotonic() + seconds
    while marker not in data:
        if time.monotonic() > end:
            return False
        if select.select([fd], [], [], .05)[0]:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                return marker in data
            if not chunk:
                return marker in data
            data.extend(chunk)
    return True


def run(shell, case, lines, before=b''):
    home = output / f'{shell.parent.parent.name}-{shell.name}-{case}'
    home.mkdir(parents=True, exist_ok=True)
    env = dict(PATH='/usr/bin:/bin', HOME=str(home), ZDOTDIR=str(home), TERM='xterm-256color', LC_ALL='C.UTF-8',
               WSH_THEME='', PS1='READY> ')
    pid, fd = pty.fork()
    if not pid:
        os.chdir(home)
        os.execve(shell, [str(shell), '-f', '-i'], env)
    data = bytearray()
    try:
        if not read_until(fd, data, b'READY> '):
            failures.append(f'{shell} {case}: no first prompt')
            return
        # Everything below is written in one go, before the shell has read any of it.
        os.write(fd, before + b''.join(lines) + b'exit\n')
        expected = [line.split(b'print ')[1].strip() for line in lines]
        read_until(fd, data, expected[-1] + b'\r\n', 15)
        read_until(fd, data, b'\x00', 3)  # Let the shell exit and flush.
        printed = ESCAPES.sub(b'', bytes(data)).replace(b'\r', b'').split(b'\n')
        seen = [marker for marker in expected if marker in printed]
        status = 'ok' if seen == expected else 'LOST ' + b' '.join(m for m in expected if m not in seen).decode()
        print(f'{status:30} {case:12} {shell}')
        if seen != expected:
            failures.append(f'{shell} {case}: {status}')
    finally:
        (home / 'transcript.bin').write_bytes(bytes(data))
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        os.waitpid(pid, 0)
        os.close(fd)


lines = [f'print TYPED_{i}\n'.encode() for i in range(1, 5)]
for shell in shells:
    # Several lines typed at once at the prompt.
    run(shell, 'at-prompt', lines)
    # Lines typed while a command runs, as when typing the next command early.
    run(shell, 'while-busy', lines, before=b'sleep 1\n')
if failures:
    raise SystemExit('FAIL: ' + '; '.join(failures))
print(f'PASS: no typed-ahead input lost in {len(shells)} shell(s)')
