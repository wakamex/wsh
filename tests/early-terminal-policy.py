#!/usr/bin/env python3
"""Exercise terminal policy when user .zshenv loads the real ZLE module."""
import argparse
import json
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import tempfile
import time

READY = b'\x1b]133;B\x1b\\'
QUERY = b'\x1b]11;?'


def launch(manager, state, home, login, opt_in):
    env = {k: v for k, v in os.environ.items() if not k.startswith('WSH_')}
    env.update(HOME=str(home), ZDOTDIR=str(home), TERM='xterm-256color',
               WSH_STATE_ROOT=str(state))
    if opt_in:
        env['WSH_ENABLE_ZLE_TERMINAL_QUERY'] = '1'
    command = [str(manager), 'run'] + (['--', '-l'] if login else [])
    started = time.monotonic()
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(home)
        os.execve(manager, command, env)
    output = b''
    exited = False
    try:
        deadline = started + 10
        while time.monotonic() < deadline:
            if select.select([fd], [], [], .05)[0]:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                output += chunk
                if READY in output:
                    return {'first_editable_ms': (time.monotonic() - started) * 1000,
                            'queries': QUERY in output,
                            'policy': output.split(b'POLICY:', 1)[-1].split(b'\r', 1)[0].decode()}
                if len(output) > 1024 * 1024:
                    raise AssertionError('unbounded terminal output')
        raise AssertionError(f'no editor readiness: {output!r}')
    finally:
        os.write(fd, b' exit\n')
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if os.waitpid(pid, os.WNOHANG)[0]:
                exited = True
                break
            time.sleep(.01)
        if not exited:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manager', type=Path)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--measure', type=int, default=0,
                        help='record default-policy startup samples without asserting query suppression')
    args = parser.parse_args()
    manager, bundle = args.manager.resolve(), args.bundle.resolve()
    with tempfile.TemporaryDirectory(prefix='wsh-early-terminal-') as directory:
        root = Path(directory)
        state = root / 'state'
        subprocess.run([manager, 'bundle', 'activate', bundle, '--state-root', state],
                       check=True, stdout=subprocess.DEVNULL)
        cases = [('default', False, '', False, None),
                 ('environment-opt-in', True, '', True, None),
                 ('user-query', False, 'query -color', True, 'query -color'),
                 ('user-no-query', True, '-query -color', False, '-query -color'),
                 ('user-no-color', False, '-color', True, '-color')]
        if args.measure:
            cases = cases[:1]
        for login in ([False] if args.measure else [False, True]):
            for name, opt_in, policy, expected_queries, expected_policy in cases:
                home = root / f'{name}-{login}'
                home.mkdir()
                script = f'typeset -ga .term.extensions=({policy})\n' if policy else ''
                script += 'autoload -Uz compinit\ncompinit -d "$ZDOTDIR/.zcompdump"\n'
                script += 'print -r -- "POLICY:${(j: :).term.extensions}"\n'
                (home / '.zshenv').write_text(script)
                (home / '.zshrc').write_text('WSH_THEME=\nPS1="WSH_QUERY_TEST> "\n')
                for iteration in range(args.measure + 1 if args.measure else 1):
                    result = launch(manager, state, home, login, opt_in)
                    print(json.dumps(dict(case=name, login=login, iteration=iteration, **result)), flush=True)
                    if not args.measure:
                        assert result['queries'] == expected_queries, (name, result)
                        if expected_policy is not None:
                            assert result['policy'] == expected_policy, (name, result)
        if not args.measure:
            print('PASS: early ZLE loading respects default, opt-in, and explicit user terminal policies')


if __name__ == '__main__':
    main()
