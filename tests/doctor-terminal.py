#!/usr/bin/env python3
"""Run doctor with a real controlling terminal and verify child cleanup."""
import json
import os
from pathlib import Path
import pty
import select
import signal
import sys
import tempfile
import time

binary = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
results = []


def alive(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()[0] != 'Z'
    except FileNotFoundError:
        return False


with tempfile.TemporaryDirectory(prefix='wsh-doctor-terminal-') as directory:
    home = Path(directory)
    (home / '.zshenv').write_text('unsetopt globalrcs\n')
    env = dict(HOME=directory, ZDOTDIR=directory, PATH='/usr/bin:/bin', TERM='xterm-256color', LC_ALL='C.UTF-8')
    for name, config, expected in [
        ('clean', '', 0),
        ('background', 'sleep 30 &\nprint -r -- $! > $HOME/background.pid\n', 0),
        ('interrupt', 'print -r -- $$ > $HOME/child.pid\nsleep 30\n', 130),
        ('timeout', 'print -r -- $$ > $HOME/child.pid\nsleep 30\n', 1),
    ]:
        (home / '.zshrc').write_text(config)
        (home / 'child.pid').unlink(missing_ok=True)
        pid, fd = pty.fork()
        if not pid:
            os.execve(binary, [str(binary), '--doctor'], env)
        transcript = bytearray()
        status = None
        sent = False
        start = time.monotonic()
        try:
            while status is None:
                assert time.monotonic() - start < 13, (name, bytes(transcript))
                if name == 'interrupt' and not sent and (home / 'child.pid').exists():
                    os.kill(pid, signal.SIGINT)
                    sent = True
                if select.select([fd], [], [], .05)[0]:
                    try:
                        transcript.extend(os.read(fd, 65536))
                    except OSError:
                        pass
                ended, value = os.waitpid(pid, os.WNOHANG)
                if ended:
                    status = value
            code = os.waitstatus_to_exitcode(status)
            assert code == expected, (name, code, bytes(transcript))
            if expected == 0:
                assert b'Plugin compatibility:' in transcript and b'error:' not in transcript, transcript
            elif name == 'timeout':
                assert b'did not finish within 10 seconds' in transcript, transcript
            if name != 'timeout':
                assert time.monotonic() - start < 5, (name, bytes(transcript))
            for marker in ('child.pid', 'background.pid'):
                path = home / marker
                if path.exists():
                    child = int(path.read_text())
                    deadline = time.monotonic() + 2
                    while alive(child) and time.monotonic() < deadline:
                        time.sleep(.01)
                    assert not alive(child), (name, marker, child)
                    path.unlink()
            results.append(dict(case=name, status=code, passed=True))
        finally:
            if status is None:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
            os.close(fd)
            (out / (name + '.bin')).write_bytes(transcript)
(out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
print('PASS: doctor controlling terminal, background cleanup, interruption and timeout')
