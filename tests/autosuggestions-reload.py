#!/usr/bin/env python3
"""Re-source a recognized zsh-autosuggestions in a live shell and check that the editor keeps working."""
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import sys
import tempfile
import time

BINARY = Path(sys.argv[1]).resolve()
PLUGIN = Path(__file__).resolve().parents[1] / 'third_party/zsh-autosuggestions/zsh-autosuggestions.zsh'
PROMPT = b'\x1b]133;B'


def check(name, condition):
    assert condition, name
    print('ok:', name)


with tempfile.TemporaryDirectory(prefix='wsh-autosuggest-reload-') as directory:
    home = Path(directory)
    shutil.copy(PLUGIN, home / 'plugin.zsh')
    # Bind Space like Oh My Zsh so a re-wrapped widget other than self-insert is exercised.
    (home / '.zshrc').write_text("source ~/plugin.zsh\nbindkey ' ' magic-space\n")
    environment = {'HOME': str(home), 'ZDOTDIR': str(home), 'PATH': '/usr/bin:/bin', 'TERM': 'xterm-256color',
                   'LC_ALL': 'C.UTF-8', 'WSH_THEME': 'minimal', 'HISTFILE': str(home / 'history')}
    pid, fd = pty.fork()
    if not pid:
        os.chdir(home)
        os.execve(BINARY, [str(BINARY), '-di'], environment)
    output = bytearray()

    def wait(token, timeout=15):
        deadline = time.monotonic() + timeout
        while token not in output and time.monotonic() < deadline:
            if select.select([fd], [], [], .05)[0]:
                output.extend(os.read(fd, 65536))
        return token in output

    def run(text, token):
        del output[:]
        os.write(fd, text)
        return wait(token)

    try:
        check('first prompt', wait(PROMPT))
        check('native owner', run(b'print -r -- OWNER-$WSH_AUTOSUGGESTIONS_OWNER-\n', b'OWNER-wsh-'))
        run(b'print -r -- WSH_RELOAD_HISTORY\n', b'WSH_RELOAD_HISTORY\r')
        check('reload', run(b'source ~/.zshrc\n', PROMPT))
        check('Enter and Space after reload', run(b'print -r -- RELOAD A B\n', b'RELOAD A B\r'))
        check('reloaded plugin owns widgets', run(b'print -r -- OWNER-$WSH_AUTOSUGGESTIONS_OWNER-\n', b'OWNER-external-active-'))
        check('no controller errors', b'file descriptor' not in output and b'No handler' not in output)
        del output[:]
        os.write(fd, b'print -r -- WSH_RELOAD_HI')
        check('suggestion after reload', wait(b'STORY'))
        check('command after suggestion', run(b'\x15print -r -- RELOAD-DONE\n', b'RELOAD-DONE\r'))
    finally:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
print('PASS: re-sourcing zsh-autosuggestions hands the editor to the reloaded plugin')
