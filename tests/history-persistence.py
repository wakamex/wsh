#!/usr/bin/env python3
"""Exercise real interactive history storage and session isolation in fresh homes."""
import hashlib
import json
import os
from pathlib import Path
import pty
import select
import shlex
import signal
import subprocess
import sys
import tempfile
import time

BINARY = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
RESULTS = []


class Shell:
    def __init__(self, home, name, env=None, args=('-dil',)):
        self.home, self.name = home, name
        self.output = bytearray()
        environment = {'HOME': str(home), 'ZDOTDIR': str(home),
                       'PATH': '/usr/bin:/bin', 'TERM': 'xterm-256color',
                       'LC_ALL': 'C.UTF-8', 'WSH_THEME': 'minimal'}
        environment.update(env or {})
        self.pid, self.fd = pty.fork()
        if not self.pid:
            os.chdir(home)
            os.execve(BINARY, [str(BINARY), *args], environment)
        try:
            self.ready()
        except BaseException:
            self.close(kill=True)
            raise

    def ready(self):
        received = bytearray()
        deadline = time.monotonic() + 15
        while b'\x1b]133;B' not in received:
            assert time.monotonic() < deadline, (self.name, bytes(received))
            if select.select([self.fd], [], [], .05)[0]:
                chunk = os.read(self.fd, 65536)
                assert chunk, self.name
                received.extend(chunk)
                self.output.extend(chunk)

    def run(self, command):
        os.write(self.fd, command.encode() + b'\n')
        self.ready()

    def close(self, kill=False):
        if self.pid is None:
            return
        try:
            if kill:
                os.killpg(self.pid, signal.SIGKILL)
            else:
                os.write(self.fd, b'exit\n')
            deadline = time.monotonic() + 10
            while True:
                child, status = os.waitpid(self.pid, os.WNOHANG)
                if child:
                    if not kill:
                        assert os.waitstatus_to_exitcode(status) == 0, status
                    break
                if time.monotonic() > deadline:
                    os.killpg(self.pid, signal.SIGKILL)
                    os.waitpid(self.pid, 0)
                    raise AssertionError(('exit timeout', self.name))
                if select.select([self.fd], [], [], .05)[0]:
                    try:
                        self.output.extend(os.read(self.fd, 65536))
                    except OSError:
                        pass
        finally:
            self.pid = None
            os.close(self.fd)
            (OUT / (self.name + '.bin')).write_bytes(self.output)


def check(name, condition):
    assert condition, name
    RESULTS.append(name)


with tempfile.TemporaryDirectory(prefix='wsh-history-') as directory:
    root = Path(directory)
    home = root / 'fresh'
    home.mkdir()
    first = Shell(home, 'first')
    second = None
    try:
        first.run('print -r -- "$HISTFILE|$HISTSIZE|$SAVEHIST|$options[incappendhistory]|$options[sharehistory]" > settings')
        check('fresh defaults', (home / 'settings').read_text().strip() ==
              f'{home}/.zsh_history|10000|10000|on|off')
        first.run(': WSH_HISTORY_BEFORE_SECOND')
        check('saved before exit', 'WSH_HISTORY_BEFORE_SECOND' in (home / '.zsh_history').read_text())
        second = Shell(home, 'second')
        second.run('fc -l 1 > before')
        check('new login reads previous history', 'WSH_HISTORY_BEFORE_SECOND' in (home / 'before').read_text())
        first.run(': WSH_HISTORY_ONLY_FIRST')
        second.run(': WSH_HISTORY_ONLY_SECOND')
        first.run('fc -l 1 > first-history')
        second.run('fc -l 1 > second-history')
        check('first session does not import live history', 'WSH_HISTORY_ONLY_SECOND' not in (home / 'first-history').read_text())
        check('second session does not import live history', 'WSH_HISTORY_ONLY_FIRST' not in (home / 'second-history').read_text())
        first.close(kill=True)
        second.close()
        saved = (home / '.zsh_history').read_text()
        check('concurrent writes and abrupt exit survive', all(x in saved for x in ('WSH_HISTORY_ONLY_FIRST', 'WSH_HISTORY_ONLY_SECOND')))
        check('history file private', (home / '.zsh_history').stat().st_mode & 0o077 == 0)
        check('no generated startup files', not any((home / p).exists() for p in ('.zshenv', '.zprofile', '.zshrc', '.zlogin')))
    finally:
        first.close(kill=True)
        if second:
            second.close(kill=True)

    cases = [
        ('zshenv-disable', '.zshenv', 'SAVEHIST=0\n', {}, None),
        ('zshrc-disable', '.zshrc', 'SAVEHIST=0\n', {}, None),
        ('unset-file', '.zshrc', 'unset HISTFILE\n', {}, None),
        ('empty-file', '.zshrc', 'HISTFILE=""\n', {}, None),
        ('environment-disable', None, '', {'SAVEHIST': '0'}, None),
        ('environment-empty-file', None, '', {'HISTFILE': ''}, None),
        ('custom-file', '.zshrc', 'HISTFILE=$HOME/custom\nHISTSIZE=73\nSAVEHIST=31\n', {}, 'custom'),
        ('environment-file', None, '', {'HISTFILE': str(root / 'inherited'), 'HISTSIZE': '73', 'SAVEHIST': '31'}, str(root / 'inherited')),
        ('explicit-sharing', '.zshrc', 'setopt share_history\n', {}, '.zsh_history'),
        ('timed-saving', '.zshrc', 'setopt inc_append_history_time extended_history\n', {}, '.zsh_history'),
        ('save-on-exit', '.zshrc', 'unsetopt inc_append_history\nsetopt append_history\n', {}, '.zsh_history'),
    ]
    for name, startup, contents, environment, expected in cases:
        home = root / name
        home.mkdir()
        if startup:
            (home / startup).write_text(contents)
        shell = Shell(home, name, environment)
        try:
            shell.run(': WSH_HISTORY_SENTINEL')
            if name == 'save-on-exit':
                check('explicit exit-only saving', not (home / '.zsh_history').exists())
            if name in ('custom-file', 'environment-file'):
                shell.run('print -r -- "$HISTSIZE|$SAVEHIST" > limits')
                check(name + ' limits', (home / 'limits').read_text().strip() == '73|31')
            if name == 'explicit-sharing':
                shell.run('print -r -- "$options[sharehistory]" > sharing')
                check('explicit sharing preserved', (home / 'sharing').read_text().strip() == 'on')
            if name == 'timed-saving':
                shell.run('print -r -- "$options[incappendhistorytime]|$options[incappendhistory]" > timing')
                check('timed saving remains effective', (home / 'timing').read_text().strip() == 'on|off')
            shell.close()
            if expected:
                check(name, 'WSH_HISTORY_SENTINEL' in (home / expected).read_text())
                if expected != '.zsh_history':
                    check(name + ' no default file', not (home / '.zsh_history').exists())
            else:
                check(name, not (home / '.zsh_history').exists())
        finally:
            shell.close(kill=True)

    home = root / 'no-rc'
    home.mkdir()
    shell = Shell(home, 'no-rc', args=('-dfil',))
    try:
        shell.run('print -r -- "${HISTFILE-unset}|$SAVEHIST|$options[incappendhistory]" > settings')
        check('no-rc keeps Zsh defaults', (home / 'settings').read_text().strip() == 'unset|0|off')
        shell.close()
        check('no-rc creates no history', not (home / '.zsh_history').exists())
    finally:
        shell.close(kill=True)

    omz = os.environ.get('WSH_TEST_OMZ')
    if omz:
        home = root / 'omz'
        home.mkdir()
        (home / '.zshrc').write_text(
            f'ZSH={shlex.quote(str(Path(omz).resolve()))}\n'
            'zstyle ":omz:update" mode disabled\nplugins=()\nZSH_THEME=""\n'
            'source "$ZSH/oh-my-zsh.sh"\n')
        shell = Shell(home, 'omz')
        try:
            shell.run('print -r -- "$HISTSIZE|$SAVEHIST|$options[sharehistory]|$options[incappendhistory]" > settings')
            check('actual OMZ history policy preserved', (home / 'settings').read_text().strip() == '50000|10000|on|off')
            shell.run(': WSH_OMZ_HISTORY')
            shell.close()
            check('actual OMZ persistence', 'WSH_OMZ_HISTORY' in (home / '.zsh_history').read_text())
        finally:
            shell.close(kill=True)

    environment = {'HOME': str(home), 'ZDOTDIR': str(home), 'PATH': '/usr/bin:/bin'}
    value = subprocess.check_output([BINARY, '-dc', 'print -r -- "${HISTFILE-unset}|$SAVEHIST|$options[incappendhistory]"'], env=environment, text=True)
    check('noninteractive keeps Zsh defaults', value.strip() == 'unset|0|off')

    home = root / 'bounded'
    home.mkdir()
    (home / '.zshrc').write_text('HISTSIZE=20\nSAVEHIST=5\n')
    shell = Shell(home, 'bounded')
    try:
        for index in range(16):
            shell.run(f': WSH_BOUNDED_{index}')
        shell.close()
        saved = (home / '.zsh_history').read_text()
        check('configured retention bounded on exit', len(saved.splitlines()) <= 5 and 'WSH_BOUNDED_15' in saved)
    finally:
        shell.close(kill=True)

(OUT / 'results.json').write_text(json.dumps({
    'binary': str(BINARY), 'binary_sha256': hashlib.sha256(BINARY.read_bytes()).hexdigest(),
    'passed': RESULTS,
}, indent=2) + '\n')
print(f'PASS: {len(RESULTS)} persistent-history and session-isolation checks')
