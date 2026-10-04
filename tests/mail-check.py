#!/usr/bin/env python3
"""Check mail notices in real interactive login sessions against mailbox times."""
import os
from pathlib import Path
import pty
import select
import signal
import sys
import tempfile
import time

BINARY = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
RESULTS = []
NEW = b'You have new mail.'
READ = b'has been read.'


class Shell:
    def __init__(self, home, name):
        self.name, self.output = name, bytearray()
        environment = {'HOME': str(home), 'ZDOTDIR': str(home), 'PATH': '/usr/bin:/bin',
                       'TERM': 'xterm-256color', 'LC_ALL': 'C.UTF-8', 'WSH_THEME': 'minimal'}
        self.pid, self.fd = pty.fork()
        if not self.pid:
            os.chdir(home)
            os.execve(BINARY, [str(BINARY), '-dil'], environment)
        self.ready()

    def ready(self):
        received = bytearray()
        deadline = time.monotonic() + 15
        while b'\x1b]133;B' not in received:
            assert time.monotonic() < deadline, (self.name, bytes(received))
            if select.select([self.fd], [], [], .05)[0]:
                chunk = os.read(self.fd, 65536)
                assert chunk, self.name
                received.extend(chunk)
        self.output.extend(received)
        return bytes(received)

    def prompt(self):
        # MAILCHECK=1 checks when more than one second has passed since the last check.
        time.sleep(2.1)
        os.write(self.fd, b':\n')
        return self.ready()

    def close(self):
        if self.pid is None:
            return
        os.killpg(self.pid, signal.SIGKILL)
        os.waitpid(self.pid, 0)
        os.close(self.fd)
        (OUT / (self.name + '.bin')).write_bytes(self.output)
        self.pid = None


def check(name, condition):
    assert condition, name
    RESULTS.append(name)


def mailbox(home, atime, mtime):
    box = home / 'mailbox'
    box.write_text('From sender\n\nbody\n')
    os.utime(box, (atime, mtime))
    (home / '.zshrc').write_text(f'MAIL={box}\nMAILCHECK=1\nsetopt mail_warning\n')
    return box


with tempfile.TemporaryDirectory(prefix='wsh-mail-') as directory:
    hour_ago = time.time() - 3600

    home = Path(directory) / 'unread'
    home.mkdir()
    box = mailbox(home, hour_ago - 10, hour_ago)
    shell = Shell(home, 'unread')
    try:
        outputs = [shell.prompt() for _ in range(3)]
        check('old unread mail is not announced', not any(NEW in output for output in outputs))
        with box.open('a') as destination:
            destination.write('From sender\n\nnew body\n')
        outputs = [shell.prompt() for _ in range(3)]
        check('new delivery is announced once', outputs[0].count(NEW) == 1 and not any(NEW in output for output in outputs[1:]))
    finally:
        shell.close()

    home = Path(directory) / 'read'
    home.mkdir()
    mailbox(home, hour_ago, hour_ago - 10)
    shell = Shell(home, 'read')
    try:
        outputs = [shell.prompt() for _ in range(3)]
        check('old read mail is not reported as newly read', not any(READ in output for output in outputs))
    finally:
        shell.close()

print('PASS:', len(RESULTS), 'mail notice timing checks')
