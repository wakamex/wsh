#!/usr/bin/env python3
"""Exercise native pane history, recovery and opt-outs through real PTYs."""
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
FAILURES = []


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


def check(name, value):
    (RESULTS if value else FAILURES).append(name)


def contents(path):
    return path.read_text() if path.exists() else ''


def pane(home, token):
    return home / 'state/wsh/history/panes' / (token + '.zsh')


def launch(home, name, token, extra=None):
    return Shell(home, name, {'XDG_STATE_HOME': str(home / 'state'),
                             'WAKTERM_PANE_TOKEN': token, **(extra or {})})


TOKEN_A = '550e8400-e29b-41d4-a716-446655440000'
TOKEN_B = '550e8400-e29b-41d4-a716-446655440001'
TOKEN_C = '550e8400-e29b-41d4-a716-446655440002'
with tempfile.TemporaryDirectory(prefix='wsh-pane-') as directory:
    root = Path(directory)
    home = root / 'normal'; home.mkdir()
    shared = home / '.zsh_history'
    shared.write_text(': SHARED_SEED\n')
    a = launch(home, 'a', TOKEN_A)
    b = launch(home, 'b', TOKEN_B)
    try:
        a.run(': PANE_A_SENTINEL')
        b.run(': PANE_B_SENTINEL')
        check('each command reaches shared history as it runs', 'PANE_A_SENTINEL' in contents(shared) and 'PANE_B_SENTINEL' in contents(shared))
        c = launch(home, 'c', TOKEN_C)
        try:
            c.run('fc -ln 1 > c-history')
            check('new pane sees running panes', 'PANE_A_SENTINEL' in contents(home / 'c-history') and 'PANE_B_SENTINEL' in contents(home / 'c-history'))
        finally: c.close(kill=True)
        a.run('print -r -- "$WSH_NATIVE_PANE_HISTORY|$HISTFILE|$options[sharehistory]" > settings')
        check('native ownership and unchanged HISTFILE', (home / 'settings').read_text().strip() == f'1|{shared}|off')
        a.close()
        check('exit merges current pane into its pane file', 'PANE_A_SENTINEL' in contents(pane(home,TOKEN_A)) and contents(shared).count('PANE_A_SENTINEL') == 1)
        b.run('fc -ln 1 > b-history')
        check('open pane does not import another pane', 'PANE_A_SENTINEL' not in contents(home / 'b-history'))
        b.close()
        check('pane files contain only their own commands', 'PANE_A_SENTINEL' in contents(pane(home,TOKEN_A)) and 'PANE_B_SENTINEL' not in contents(pane(home,TOKEN_A)) and 'SHARED_SEED' not in contents(pane(home,TOKEN_A)))
    finally:
        a.close(kill=True); b.close(kill=True)
    a = launch(home, 'recall', TOKEN_A)
    try:
        a.run('fc -ln 1 > recall')
        history = contents(home / 'recall')
        check('shared history followed by pane history', history.rfind('PANE_A_SENTINEL') > history.rfind('PANE_B_SENTINEL') >= 0)
        a.run(': CRASH_SENTINEL')
        a.close(kill=True)
        check('abrupt exit retains journal', 'CRASH_SENTINEL' in contents(Path(str(pane(home,TOKEN_A))+'.journal')))
    finally: a.close(kill=True)
    a = launch(home, 'recover', TOKEN_A)
    try:
        check('restart merges crashed commands', contents(shared).count('CRASH_SENTINEL') == 1 and 'CRASH_SENTINEL' in contents(pane(home,TOKEN_A)))
        a.run('fc -ln 1 > recovered')
        check('restart recalls crashed commands', 'CRASH_SENTINEL' in contents(home / 'recovered'))
        a.run(': EXEC_SENTINEL')
        a.run('exec ' + shlex.quote(str(BINARY)) + ' -dil')
        check('exec recovers same-pane journal', 'EXEC_SENTINEL' in contents(shared))
        a.run(shlex.quote(str(BINARY)) + ' -dil')
        a.run(': NESTED_SENTINEL')
        a.run('exit')
        a.run(': OUTER_SENTINEL')
        a.close()
        check('nested shell uses shared history', 'NESTED_SENTINEL' in contents(shared) and 'NESTED_SENTINEL' not in contents(pane(home,TOKEN_A)))
        check('outer shell retains ownership', 'OUTER_SENTINEL' in contents(pane(home,TOKEN_A)))
        check('private file permissions', all(p.stat().st_mode & 0o077 == 0 for p in (home / 'state/wsh/history/panes').iterdir() if p.is_file()))
    finally: a.close(kill=True)

    for name, rc, extra in [
        ('zero', 'SAVEHIST=0', {}), ('empty', 'HISTFILE=""', {}), ('unset', 'unset HISTFILE', {}),
        ('skip', '', {'WAKTERM_SHELL_SKIP_PANE_HISTORY':'1'}),
        ('invalid', '', {'WAKTERM_PANE_TOKEN':'../../outside'}),
        ('context', 'fc -p', {}),
    ]:
        home = root / name; home.mkdir(); (home / '.zshrc').write_text(rc+'\n')
        a = launch(home, name, TOKEN_A, extra)
        try:
            a.run(': OPT_OUT_SENTINEL'); a.close()
            check(name+' does not create pane storage', not (home/'state/wsh/history/panes').exists())
            if name in ('zero','empty','unset','context'):
                check(name+' does not save private command', 'OPT_OUT_SENTINEL' not in contents(home/'.zsh_history'))
        finally: a.close(kill=True)

    home=root/'modes';home.mkdir()
    environment={'XDG_STATE_HOME':str(home/'state'),'WAKTERM_PANE_TOKEN':TOKEN_A}
    a=Shell(home,'no-rc',environment,args=('-dfil',))
    try:a.run(': NO_RC_SENTINEL');a.close()
    finally:a.close(kill=True)
    check('no-rc ignores pane token', not (home/'state').exists() and not (home/'.zsh_history').exists())
    subprocess.run([BINARY,'-dc',':'],check=True,env={'HOME':str(home),'ZDOTDIR':str(home),'PATH':'/usr/bin:/bin',**environment})
    check('noninteractive ignores pane token', not (home/'state').exists())

    home=root/'duplicate-owner';home.mkdir()
    a=launch(home,'owner-first',TOKEN_A)
    b=launch(home,'owner-second',TOKEN_A)
    try:
        a.run(': OWNER_FIRST_SENTINEL')
        b.run(': OWNER_SECOND_SENTINEL')
        b.close();a.close()
        check('duplicate token falls back without writing pane journal', 'OWNER_FIRST_SENTINEL' in contents(pane(home,TOKEN_A)) and 'OWNER_SECOND_SENTINEL' not in contents(pane(home,TOKEN_A)) and 'OWNER_SECOND_SENTINEL' in contents(home/'.zsh_history'))
    finally:a.close(kill=True);b.close(kill=True)

    home=root/'private-context';home.mkdir()
    a=launch(home,'private-context',TOKEN_A)
    try:
        a.run(': PUBLIC_SENTINEL')
        a.run('fc -p')
        a.run(': PRIVATE_SENTINEL')
        a.run('fc -P')
        a.close()
        check('private context is excluded from pane and shared files', all('PRIVATE_SENTINEL' not in contents(p) for p in home.rglob('*') if p.is_file()))
        check('public context still merges', 'PUBLIC_SENTINEL' in contents(home/'.zsh_history'))
    finally:a.close(kill=True)

    home=root/'failure';home.mkdir()
    (home/'.zshrc').write_text('HISTFILE=$HOME/missing/history\n')
    a=launch(home,'merge-failure',TOKEN_A)
    try:
        for i in range(3):a.run(f': UNSAVED_{i}')
        a.close()
    finally:a.close(kill=True)
    check('unwritable shared file keeps each command once in pane history', all(contents(pane(home,TOKEN_A)).count(f'UNSAVED_{i}') == 1 for i in range(3)))
    (home/'missing').mkdir()
    a=launch(home,'merge-retry',TOKEN_A)
    try:a.run(': RETRY_SENTINEL');a.close()
    finally:a.close(kill=True)
    check('writable shared file receives later commands', 'RETRY_SENTINEL' in contents(home/'missing/history'))

    home=root/'legacy';home.mkdir()
    directory=pane(home,TOKEN_A).parent;directory.mkdir(parents=True);directory.chmod(0o700)
    legacy=Path(str(pane(home,TOKEN_A))+'.pending');legacy.write_text(': 1700000000:0;: LEGACY_SENTINEL\n');legacy.chmod(0o600)
    a=launch(home,'legacy',TOKEN_A)
    try:a.close()
    finally:a.close(kill=True)
    check('earlier pending journal reaches shared and pane files', 'LEGACY_SENTINEL' in contents(home/'.zsh_history') and 'LEGACY_SENTINEL' in contents(pane(home,TOKEN_A)) and not legacy.exists())

    home=root/'omz-sharing';home.mkdir()
    (home/'.zshrc').write_text('omz_history() { :; }\nsetopt share_history\n')
    a=launch(home,'omz-sharing',TOKEN_A)
    try:
        a.run('print -r -- "$options[sharehistory]" > sharing');a.close()
        check('Oh My Zsh live sharing is turned off', (home/'sharing').read_text().strip() == 'off')
    finally:a.close(kill=True)

    home=root/'bounded';home.mkdir()
    (home/'.zshrc').write_text('HISTSIZE=20\nSAVEHIST=5\nsetopt inc_append_history_time extended_history\n')
    a=launch(home,'bounded',TOKEN_A)
    try:
        for i in range(16):a.run(f': BOUNDED_{i}')
        a.close()
        check('pane and shared retention', all(len(contents(p).splitlines()) <= 5 and 'BOUNDED_15' in contents(p) for p in (pane(home,TOKEN_A),home/'.zsh_history')))
    finally:a.close(kill=True)

    home=root/'custom';home.mkdir()
    (home/'.zshrc').write_text('export HISTFILE=$HOME/custom-history\nsetopt share_history\n')
    a=launch(home,'custom',TOKEN_A)
    try:
        a.run(': CUSTOM_OUTER_SENTINEL')
        a.run('print -r -- "$options[sharehistory]" > sharing')
        a.run(shlex.quote(str(BINARY))+' -dil')
        a.run(': CUSTOM_NESTED_SENTINEL')
        a.run('exit')
        a.close()
        check('exported custom shared path survives nesting', 'CUSTOM_NESTED_SENTINEL' in contents(home/'custom-history') and 'CUSTOM_NESTED_SENTINEL' not in contents(pane(home,TOKEN_A)))
        check('explicit live sharing keeps pane history', 'CUSTOM_OUTER_SENTINEL' in contents(pane(home,TOKEN_A)) and (home/'sharing').read_text().strip() == 'on' and not (home/'.zsh_history').exists())
    finally:a.close(kill=True)

    home=root/'symlink';home.mkdir()
    directory=pane(home,TOKEN_A).parent;directory.mkdir(parents=True)
    directory.chmod(0o700)
    victim=home/'victim';victim.write_text('unchanged\n')
    for suffix in ('.pending', '.journal'):
        link=Path(str(pane(home,TOKEN_A))+suffix)
        link.unlink(missing_ok=True)
        link.symlink_to(victim)
        a=launch(home,'symlink'+suffix,TOKEN_A)
        try:
            a.run(': SYMLINK_SENTINEL'+suffix.replace('.','_'));a.close()
            check('symlink '+suffix+' rejected without touching target', contents(victim)=='unchanged\n' and 'unchanged' not in contents(home/'.zsh_history') and 'SYMLINK_SENTINEL'+suffix.replace('.','_') in contents(home/'.zsh_history'))
        finally:a.close(kill=True)
        link.unlink()

    home=root/'unavailable';home.mkdir();(home/'state').write_text('not a directory')
    a=launch(home,'unavailable',TOKEN_A)
    try:
        a.run(': FALLBACK_SENTINEL');a.close()
        check('unavailable state preserves ordinary history', 'FALLBACK_SENTINEL' in contents(home/'.zsh_history'))
    finally:a.close(kill=True)

    omz=os.environ.get('WSH_TEST_OMZ')
    if omz:
        home=root/'omz';home.mkdir()
        (home/'.zshrc').write_text('ZSH='+shlex.quote(str(Path(omz).resolve()))+'\nzstyle ":omz:update" mode disabled\nplugins=()\nZSH_THEME=""\nsource "$ZSH/oh-my-zsh.sh"\n')
        a=launch(home,'omz',TOKEN_A)
        try:
            a.run(': OMZ_PANE_SENTINEL')
            check('OMZ pane publishes commands as they run', 'OMZ_PANE_SENTINEL' in contents(home/'.zsh_history'))
            a.close()
            check('OMZ pane merges on exit', contents(home/'.zsh_history').count('OMZ_PANE_SENTINEL') == 1 and 'OMZ_PANE_SENTINEL' in contents(pane(home,TOKEN_A)))
        finally:a.close(kill=True)

    adapter=os.environ.get('WSH_TEST_WAKTERM')
    if adapter:
        home=root/'adapter';home.mkdir()
        (home/'.zshrc').write_text('source '+shlex.quote(str(Path(adapter).resolve()))+'\n')
        a=launch(home,'adapter',TOKEN_A)
        try:
            a.run(': ADAPTER_SENTINEL');a.close()
            check('real Wakterm adapter yields to native ownership', 'ADAPTER_SENTINEL' in contents(pane(home,TOKEN_A)) and not (home/'state/wakterm/pane-history').exists())
        finally:a.close(kill=True)

(OUT/'results.json').write_text(json.dumps({'binary':str(BINARY),'binary_sha256':hashlib.sha256(BINARY.read_bytes()).hexdigest(),'passed':RESULTS,'failed':FAILURES},indent=2)+'\n')
assert not FAILURES, FAILURES
print(f'PASS: {len(RESULTS)} native pane-history checks')
