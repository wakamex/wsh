#!/usr/bin/env python3
"""Temporary macOS diagnosis: type into Wsh step by step and report whether it survives each key."""
import os, pty, select, signal, sys, time
from pathlib import Path
wsh = Path(sys.argv[1]).absolute()
home = Path(sys.argv[2]).resolve(); home.mkdir(parents=True, exist_ok=True)
(home / '.zshrc').write_text('print -s "print -r -- WSH_MATCH_OLDER"\nprint -s "print -r -- WSH_MATCH_NEWER"\n')
env = dict(PATH='/usr/bin:/bin', HOME=str(home), ZDOTDIR=str(home), TERM='xterm-256color', LC_ALL='C.UTF-8', WSH_THEME='')
pid, fd = pty.fork()
if not pid:
    os.chdir(home); os.execve(wsh, [str(wsh), '-d', '-i'], env)
data = bytearray()
def pump(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if select.select([fd], [], [], .05)[0]:
            try: chunk = os.read(fd, 65536)
            except OSError: return 'eof'
            if not chunk: return 'eof'
            data.extend(chunk)
    return 'open'
def status():
    try: got, st = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError: return 'reaped'
    if not got: return 'alive'
    if os.WIFSIGNALED(st): return f'killed by signal {os.WTERMSIG(st)}'
    return f'exited {os.WEXITSTATUS(st)}'
pump(3)
for label, keys in [('type wsh_match', b'wsh_match'), ('Up: history search', b'\x1bOA'), ('Ctrl+E', b'\x05'),
                    ('Ctrl+U', b'\x15'), ('type print, autosuggest', b'print -r -- WSH'), ('Right: accept', b'\x1b[C'),
                    ('Enter', b'\r')]:
    before = len(data)
    os.write(fd, keys)
    state = pump(2)
    print(f'{label:26} tty={state:5} shell={status():22} output={bytes(data[before:])[-300:]!r}', flush=True)
    if status() != 'alive':
        break
os.kill(pid, signal.SIGKILL) if status() == 'alive' else None
