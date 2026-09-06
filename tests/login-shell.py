#!/usr/bin/env python3
"""Real execve and PTY login-style checks; no account or PAM changes."""
import copy
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time

manager, bundle = [str(Path(p).resolve()) for p in sys.argv[1:3]]
scratch = Path(tempfile.mkdtemp(prefix='wsh-login-shell-'))
scratch.chmod(0o755)
home, state = scratch / 'home', scratch / 'state'
home.mkdir(mode=0o755)
state.mkdir(mode=0o755)
env = {k: v for k, v in os.environ.items() if not k.startswith(('WSH_', 'ZSH_', 'WAKTERM_')) and k not in ('ZDOTDIR', 'XDG_DATA_HOME', 'BASH_ENV', 'ENV')}
env.update(HOME=str(home), ZDOTDIR=str(home), WSH_STATE_ROOT=str(state), WSH_THEME='', TERM='xterm-256color')
statefile = state / 'bundle-state.json'

def launch(argv0, args, environment=None, drop_uid=False):
    preexec = (lambda: os.setuid(65534)) if drop_uid and os.geteuid() == 0 else None
    return subprocess.run([argv0] + args, executable=manager, env=environment or env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, preexec_fn=preexec)

def check_recovery(label, drop_uid=False):
    for argv0, args in [('-wsh', ['-c']), (manager, ['-c']), (manager, ['-lc']), (manager, ['--login', '-c'])]:
        result = launch(argv0, args + ['printf "RECOVERED:%s:%s" "$SHELL" "${WSH_BUNDLE_ROOT-unset}"; exit 37'], drop_uid=drop_uid)
        assert result.returncode == 37 and result.stdout == b'RECOVERED:/bin/bash:unset', (label, argv0, args, result.returncode, result.stdout, result.stderr)
        assert b'system Bash recovery' in result.stderr, (label, result.stderr)
    print('PASS: ' + label + ' preserves login and command access', flush=True)

def write_state(value):
    statefile.write_text(json.dumps(value))

def pty_recovery():
    pid, fd = pty.fork()
    if pid == 0:
        poisoned = env.copy()
        poisoned.update(PROMPT_COMMAND='echo STARTUP_POISON; exit 88', PS0='$(echo STARTUP_POISON)',
                        BASH_ENV=str(home / 'poison-env'), ENV=str(home / 'poison-env'))
        poisoned['BASH_FUNC_exit%%'] = '() { echo STARTUP_POISON; builtin exit 88; }'
        os.execve(manager, ['-wsh'], poisoned)
    output = bytearray()
    def wait(marker, offset=0):
        deadline = time.monotonic() + 8
        while marker not in output[offset:]:
            assert time.monotonic() < deadline, ('PTY timeout', marker, bytes(output))
            if select.select([fd], [], [], .1)[0]:
                output.extend(os.read(fd, 65536))
    try:
        wait(b'wsh recovery$ ')
        offset = len(output)
        os.write(fd, b'/bin/sleep 30\r')
        # Wait for echo, then allow the actual foreground job to acquire the terminal.
        wait(b'/bin/sleep 30', offset)
        time.sleep(.1)
        os.write(fd, b'\x1a')
        wait(b'Stopped', offset)
        wait(b'wsh recovery$ ', offset)
        offset = len(output)
        os.write(fd, b'fg\r')
        wait(b'/bin/sleep 30', offset)
        time.sleep(.1)
        os.write(fd, b'\x03')
        wait(b'wsh recovery$ ', offset)
        offset = len(output)
        os.write(fd, b'printf "PTY_%s\\n" ACCESS; exit 23\r')
        wait(b'PTY_ACCESS', offset)
        deadline = time.monotonic() + 5
        while True:
            waited, status = os.waitpid(pid, os.WNOHANG)
            if waited:
                assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 23, status
                pid = None
                break
            assert time.monotonic() < deadline, 'recovery shell did not exit'
            time.sleep(.01)
        assert b'STARTUP_POISON' not in output
    finally:
        os.close(fd)
        if pid is not None:
            os.kill(pid, signal.SIGHUP)
            os.waitpid(pid, 0)
    print('PASS: login argv[0] reaches a PTY prompt with Ctrl-Z, fg, Ctrl-C and exact exit status', flush=True)

try:
    check_recovery('missing activation state')
    # A home with startup loops must not be read by recovery Bash.
    for name in ('.bash_profile', '.bash_login', '.profile', '.bashrc', 'poison-env'):
        (home / name).write_text('echo STARTUP_POISON; exit 88\n')
    poisoned = env.copy()
    poisoned.update(BASH_ENV=str(home / 'poison-env'), ENV=str(home / 'poison-env'),
                    SHELL=manager, WSH_BUNDLE_ROOT='/missing/inherited', WSH_RUNTIME='/missing/runtime',
                    WSH_NATIVE_TERMINAL_INTEGRATION='1')
    result = launch('-wsh', ['-lc', 'printf "%s\\n" "$0" "$@"; exit 19', 'session-name', 'space value', b'raw-\xff'], poisoned)
    assert result.returncode == 19 and result.stdout == b'session-name\nspace value\nraw-\xff\n', (result.stdout, result.stderr)
    assert b'STARTUP_POISON' not in result.stderr
    for args in (['update'], ['run'], ['--version', 'extra'], ['-o', 'not-a-bash-option'], ['-c']):
        result = launch(manager, args)
        assert result.returncode != 0 and b'system Bash recovery' not in result.stderr, (args, result.stderr)
    result = launch('-wsh', ['script.zsh'])
    assert result.returncode != 0 and b'system Bash recovery' not in result.stderr, result.stderr
    print('PASS: recovery skips poisoned startup files, preserves argv bytes, and leaves manager/script/unsupported-option errors intact', flush=True)
    pty_recovery()
    subprocess.run([manager, 'bundle', 'activate', bundle, '--state-root', str(state)], check=True, stdout=subprocess.PIPE)
    valid = json.loads(statefile.read_text())
    # State can still exist while a login service supplies a different environment.
    changed_env = env.copy()
    changed_env.pop('WSH_STATE_ROOT')
    changed_env['XDG_DATA_HOME'] = str(scratch / 'different-data-home')
    result = launch('-wsh', ['-c', 'printf ENVIRONMENT_RECOVERED'], changed_env)
    assert result.returncode == 0 and result.stdout == b'ENVIRONMENT_RECOVERED'
    assert json.loads(statefile.read_text()) == valid
    changed_env.pop('HOME')
    changed_env.pop('XDG_DATA_HOME')
    result = launch('-wsh', ['-c', 'printf NO_HOME_RECOVERED'], changed_env)
    assert result.returncode == 0 and result.stdout == b'NO_HOME_RECOVERED'
    print('PASS: changed state-location environment and absent HOME recover without changing existing state', flush=True)
    for suffix, version in [('incompatible', 999), ('old', 1)]:
        changed = copy.deepcopy(valid)
        changed['version'] = version
        write_state(changed)
        check_recovery(suffix + ' state version')
    statefile.write_text('{broken')
    check_recovery('malformed JSON')
    write_state(valid)
    statefile.chmod(0)
    check_recovery('unreadable state', drop_uid=True)
    statefile.chmod(0o600)
    statefile.unlink()
    statefile.symlink_to(scratch / 'absent')
    check_recovery('symlink state')
    statefile.unlink()
    changed = copy.deepcopy(valid)
    changed['active']['path'] = str(scratch / 'absent-bundle')
    write_state(changed)
    check_recovery('missing bundle')
    damaged = scratch / 'damaged-bundle'
    shutil.copytree(bundle, str(damaged))
    changed['active']['path'] = str(damaged)
    write_state(changed)
    shell = damaged / changed['active']['launch']['shell']['path']
    original = shell.read_bytes()
    shell.write_bytes(b'broken')
    check_recovery('entrypoint metadata mismatch')
    shell.write_bytes(b'#!/wsh-missing-interpreter\n' + b' ' * (len(original) - len(b'#!/wsh-missing-interpreter\n')))
    check_recovery('exec-time missing interpreter')
    write_state(valid)
    # Healthy login startup must still belong to Zsh, and -c must preserve its exit status.
    (home / '.zshenv').write_text('print -r -- ENV >> "$HOME/order"\n')
    (home / '.zprofile').write_text('print -r -- PROFILE >> "$HOME/order"\n')
    (home / '.zlogin').write_text('print -r -- LOGIN >> "$HOME/order"\n')
    (home / '.zshrc').write_text('WSH_THEME=""\n')
    for argv0, flags in [('-wsh', ['-c']), (manager, ['-lc']), (manager, ['--login', '-c'])]:
        order = home / 'order'
        if order.exists(): order.unlink()
        result = launch(argv0, flags + ['[[ -o login ]] || exit 90; print -r -- "ZSH:$ZSH_VERSION"; exit 41'])
        assert result.returncode == 41 and result.stdout.startswith(b'ZSH:5.9.'), (result.returncode, result.stdout, result.stderr)
        assert order.read_text().splitlines() == ['ENV', 'PROFILE', 'LOGIN']
        assert b'recovery' not in result.stderr
    result = launch(manager, ['-c', '[[ ! -o login ]] || exit 90; exit 43'])
    assert result.returncode == 43 and b'recovery' not in result.stderr
    print('PASS: healthy shell invocations preserve Zsh login startup, non-login -c, and command exit status', flush=True)
finally:
    if statefile.exists() and not statefile.is_symlink(): statefile.chmod(0o600)
    shutil.rmtree(str(scratch))
