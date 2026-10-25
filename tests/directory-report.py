#!/usr/bin/env python3
"""Check that the terminal's directory report (OSC 7) names the shell's own directory.

Usage: directory-report.py WSH OUTPUT

A cd inside a subshell must not report the subshell's directory, and `wsh --run` reports its
command's directory before the command starts.
"""
import faulthandler
import os
from pathlib import Path
import pty
import re
import select
import signal
import socket
import sys
import time

# Wsh finds its resources from the path it was started by, so keep bin/wsh unresolved.
wsh = Path(sys.argv[1]).absolute()
output = Path(sys.argv[2]).resolve()
output.mkdir(parents=True, exist_ok=True)
# A hang prints every thread's stack and fails instead of stalling the suite.
faulthandler.dump_traceback_later(120, exit=True)
REPORT = re.compile(rb'\x1b\]7;file://[^/]*(/[^\x1b]*)\x1b\\')
checks = 0


def check(name, condition, detail=''):
    global checks
    assert condition, f'{name}: {detail}'
    checks += 1


def start(name, config, argv):
    home = output / name
    (home / 'work').mkdir(parents=True, exist_ok=True)
    (home / 'elsewhere').mkdir(exist_ok=True)
    (home / '.zshrc').write_text(config)
    env = dict(PATH='/usr/bin:/bin', HOME=str(home), ZDOTDIR=str(home), TERM='xterm-256color', LC_ALL='C.UTF-8',
               WSH_THEME='', HOST=socket.gethostname())
    pid, fd = pty.fork()
    if not pid:
        os.chdir(home / 'work')
        os.execve(wsh, ['wsh', *argv], env)
    return home, pid, fd


def read_until(fd, data, marker, seconds=20):
    end = time.monotonic() + seconds
    while marker not in data:
        assert time.monotonic() < end, bytes(data[-1500:])
        if select.select([fd], [], [], .05)[0]:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            data.extend(chunk)
    return data


def reports(data):
    return [Path(os.fsdecode(path)) for path in REPORT.findall(bytes(data))]


def reaped(pid, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if os.waitpid(pid, os.WNOHANG) != (0, 0):
            return True
        time.sleep(.05)
    return False


def stop(home, pid, fd, data):
    (home / 'transcript.bin').write_bytes(bytes(data))
    # A shell that ignores the hangup is killed, so a stuck child cannot stall the suite.
    os.kill(pid, signal.SIGHUP)
    if not reaped(pid, 5):
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    os.close(fd)


# A startup file that changes directory in a subshell, as background helpers often do.
SUBSHELL = '(cd $HOME/elsewhere && :)\n(cd $HOME/elsewhere && sleep 0 &!)\n'

# wsh --run: every report before and while the command runs names the command's directory.
home, pid, fd = start('run', SUBSHELL, ['--run', '--login', '--', 'sh', '-c', 'printf "RUNNING\\n"; sleep 1; printf "ENDING\\n"'])
data = bytearray()
try:
    read_until(fd, data, b'RUNNING')
    before = reports(data)
    check('a report precedes the command', bool(before), bytes(data[-800:]))
    check('reports before the command name its directory', set(before) == {home / 'work'}, before)
    read_until(fd, data, b'ENDING')
    check('no report names the subshell directory', home / 'elsewhere' not in reports(data), reports(data))
finally:
    stop(home, pid, fd, data)

# Interactive shell: a subshell cd is silent, and the shell's own cd is still reported.
home, pid, fd = start('interactive', SUBSHELL, ['-di'])
data = bytearray()
try:
    read_until(fd, data, b'\x1b]133;B')
    offset = len(data)
    os.write(fd, b'(cd $HOME/elsewhere && print SUBSHELL-$PWD); print -r -- $(cd / && print DONE)\n')
    read_until(fd, data, b'DONE')
    read_until(fd, data, b'\x1b]133;B', 20)
    check('subshell cd at the prompt is not reported', home / 'elsewhere' not in reports(data) and Path('/') not in reports(data[offset:]),
          reports(data[offset:]))
    offset = len(data)
    os.write(fd, b'cd $HOME/elsewhere\n')
    end = time.monotonic() + 20
    while home / 'elsewhere' not in reports(data[offset:]):
        assert time.monotonic() < end, bytes(data[-800:])
        if select.select([fd], [], [], .05)[0]:
            data.extend(os.read(fd, 65536))
    check('the shell\'s own cd is reported', home / 'elsewhere' in reports(data[offset:]))
finally:
    stop(home, pid, fd, data)
print(f'PASS: {checks} directory report checks')
