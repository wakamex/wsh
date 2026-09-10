#!/usr/bin/env python3
"""Exercise the real OMZ collector and prompt ownership through an interactive PTY."""
import json
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import signal
import subprocess
import sys
import time

bundle, out = (Path(v).resolve() for v in sys.argv[1:])
out.mkdir(parents=True, exist_ok=True)
rows = []
for case in ('wsh', 'existing', 'failed-theme', 'modified-plugin', 'modified-collector', 'overridden-hook', 'absent'):
    home = out / case
    home.mkdir()
    (home / 'sub').mkdir()
    git_env = dict(PATH='/usr/bin:/bin', HOME=str(home), GIT_CONFIG_NOSYSTEM='1')
    subprocess.run(['git', 'init', '-q', '-b', 'main', home], env=git_env, check=True)
    subprocess.run(['git', '-C', home, '-c', 'user.name=Wsh test', '-c', 'user.email=test@wsh.invalid', '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '--allow-empty', '-qm', 'fixture'], env=git_env, check=True)
    plugin = home / 'plugin'
    shutil.copytree(bundle / 'share/wsh/defaults/oh-my-zsh-git-prompt', plugin)
    if case == 'modified-plugin':
        with (plugin / 'git-prompt.plugin.zsh').open('a') as f:
            f.write('\n# local modification\n')
    if case == 'modified-collector':
        with (plugin / 'gitstatus.py').open('a') as f:
            f.write('\n# local modification\n')
    bindir = home / 'bin'
    bindir.mkdir()
    python = bindir / 'python3'
    python.write_text('#!/bin/sh\nprintf "collector\\n" >> "$WSH_TEST_COLLECTOR_LOG"\nexec /usr/bin/python3 "$@"\n')
    python.chmod(0o755)
    config = '''PROMPT='EXISTING> '
ZSHZ_DATA=$HOME/jump-data
WSH_DISABLE_AUTOSUGGESTIONS=1
WSH_DISABLE_SYNTAX_HIGHLIGHTING=1
WSH_DISABLE_HISTORY_SUBSTRING_SEARCH=1
autoload -Uz add-zsh-hook
user_precmd() { print -r -- user >> $HOME/user-hooks; }
add-zsh-hook precmd user_precmd
'''
    if case != 'absent':
        config += 'source ' + shlex.quote(str(plugin / 'git-prompt.plugin.zsh')) + '\n'
    if case == 'overridden-hook':
        config += 'precmd_update_git_vars() { update_current_git_vars; }\n'
    config += 'typeset -g saved_rprompt=$RPROMPT\n'
    (home / '.zshrc').write_text(config)
    (home / '.zshenv').write_text('unsetopt globalrcs\n')
    theme = '' if case == 'existing' else str(home / 'missing-theme.toml') if case == 'failed-theme' else 'minimal'
    log = home / 'collector.log'
    env = dict(PATH=str(bindir) + ':/usr/bin:/bin', HOME=str(home), ZDOTDIR=str(home), TERM='xterm-256color', LC_ALL='C.UTF-8', WSH_THEME=theme, WSH_TEST_COLLECTOR_LOG=str(log))
    pid, fd = pty.fork()
    if not pid:
        os.chdir(home)
        os.execve(bundle / 'bin/wsh', ['wsh', '-di'], env)
    data = bytearray()
    def wait(marker, start=0):
        deadline = time.monotonic() + 15
        while marker not in data[start:]:
            assert time.monotonic() < deadline, (case, bytes(data[-2000:]))
            if select.select([fd], [], [], .05)[0]:
                data.extend(os.read(fd, 65536))
    try:
        wait(b'\x1b]133;B')
        for command in (b':\n', b'cd sub\n', b'git status >/dev/null 2>&1\n'):
            offset = len(data)
            os.write(fd, command)
            wait(b'\x1b]133;B', offset)
        offset = len(data)
        os.write(fd, b"print -r -- $'\\x1eSTATE:'\"$WSH_PROMPT_OWNER|$WSH_GIT_PROMPT_OWNER|${precmd_functions[(Ie)precmd_update_git_vars]}|${preexec_functions[(Ie)preexec_update_git_vars]}|${chpwd_functions[(Ie)chpwd_update_git_vars]}\"$'\\x1f'\n")
        wait(b'\x1eSTATE:', offset)
        begin = data.index(b'\x1eSTATE:', offset) + 7
        wait(b'\x1f', begin)
        state = bytes(data[begin:data.index(b'\x1f', begin)]).decode()
        wait(b'\x1b]133;B', offset)
        prompt, owner, *hooks = state.split('|')
        expected = 'wsh' if case == 'wsh' else 'absent' if case == 'absent' else 'external' if case in ('existing', 'failed-theme') else 'external-unknown'
        assert owner == expected, (case, state)
        calls = len(log.read_text().splitlines()) if log.exists() else 0
        if case in ('wsh', 'absent'):
            assert hooks == ['0', '0', '0'] and calls == 0, (case, state, calls)
        else:
            assert all(int(h) > 0 for h in hooks) and calls > 0, (case, state, calls)
        assert prompt == ('existing' if case in ('existing', 'failed-theme') else 'wsh'), state
        assert len((home / 'user-hooks').read_text().splitlines()) >= 5
        rows.append(dict(case=case, state=state, collector_calls=calls, passed=True))
    finally:
        (home / 'transcript.bin').write_bytes(data)
        os.kill(pid, signal.SIGHUP)
        os.waitpid(pid, 0)
        os.close(fd)
(out / 'results.json').write_text(json.dumps(rows, indent=2) + '\n')
print('PASS: real git-prompt collection, prompt ownership, failed-theme fallback and preserved custom hooks')
