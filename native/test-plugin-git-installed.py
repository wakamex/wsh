#!/usr/bin/env python3
"""Verify an actual uncataloged upstream checkout through installed ZLE."""
import json
import os
from pathlib import Path
import pty
import select
import shlex
import signal
import sys
import time

bundle, plugin, output = [Path(p).resolve() for p in sys.argv[1:]]
output.mkdir(parents=True, exist_ok=True)
rows = []
for theme in ('', 'minimal'):
    home = output / (theme or 'existing')
    home.mkdir(exist_ok=True)
    config = 'PROMPT="UPSTREAM> "\nHISTSIZE=100\nSAVEHIST=0\nsource ' + shlex.quote(str(plugin)) + '\n'
    config += '''WSH_AUTOSUGGEST_ASYNC=0
ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE=fg=blue
print -s -- 'echo needle upstream'
_observe() { print -nr -- $'\x1eEDITOR:'"$BUFFER|$POSTDISPLAY"$'\x1f'; }
zle -N _observe
bindkey '^T' _observe
'''
    (home/'.zshrc').write_text(config)
    env = dict(PATH='/usr/bin:/bin', HOME=str(home), ZDOTDIR=str(home), TERM='xterm-256color', LC_ALL='C.UTF-8', WSH_THEME=theme)
    pid, fd = pty.fork()
    if not pid:
        os.chdir(home)
        os.execve(bundle/'bin/wsh', ['wsh', '-di'], env)
    data = bytearray()
    def wait(marker, offset=0):
        deadline = time.monotonic()+10
        while marker not in data[offset:]:
            assert time.monotonic() < deadline, bytes(data[-1500:])
            if select.select([fd], [], [], .05)[0]:
                data.extend(os.read(fd, 65536))
    try:
        wait(b'\x1b]133;B')
        offset = len(data)
        os.write(fd, b"[[ $WSH_AUTOSUGGESTIONS_OWNER == wsh && $ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE == fg=blue && ${(j:,:)ZSH_AUTOSUGGEST_IGNORE_WIDGETS} == *zle-* && ${+functions[_wsh_plugin_git]} == 0 ]] && print -r -- $'\\x1eNATIVE-OWNER\\x1f'\n")
        wait(b'\x1eNATIVE-OWNER\x1f', offset)
        wait(b'\x1b]133;B', offset)
        offset = len(data)
        os.write(fd, b'echo need')
        time.sleep(.05)
        os.write(fd, b'\x14')
        wait(b'\x1eEDITOR:echo need|le upstream\x1f', offset)
        offset = len(data)
        os.write(fd, b'\x1b[C\x14')
        wait(b'\x1eEDITOR:echo needle upstream|\x1f', offset)
        rows.append(dict(theme=theme or 'existing', owner='wsh', style=True, legacy_ignore=True, helpers_removed=True, displayed=True, accepted=True))
    finally:
        (home/'transcript.bin').write_bytes(data)
        os.kill(pid, signal.SIGHUP)
        os.waitpid(pid, 0)
        os.close(fd)
(output/'results.json').write_text(json.dumps(rows, indent=2)+'\n')
print('PASS: uncataloged upstream native ownership, legacy ignore, styles, display, accept and helper cleanup under both prompt owners')
