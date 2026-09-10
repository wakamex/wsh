#!/usr/bin/env python3
"""Check real OMZ loading, ownership and doctor advice through an interactive PTY."""
import json
import os
from pathlib import Path
import pty
import select
import shlex
import signal
import sys
import subprocess
import time

bundle, omz, output = [Path(p).resolve() for p in sys.argv[1:]]
output.mkdir(parents=True, exist_ok=True)
rows = []
for case in ('pending', 'active', 'modified', 'disabled', 'automatic', 'older-pending', 'older-active', 'older-modified', 'older-disabled', 'older-automatic', 'older-custom'):
    mode = case.split('-', 1)[1] if case.startswith('older-') else case
    reference = 'known-zsh-autosuggestions-0.7.0.zsh' if case.startswith('older-') else 'zsh-autosuggestions.zsh'
    home = output / case
    plugin = home / 'custom/plugins/zsh-autosuggestions/zsh-autosuggestions.plugin.zsh'
    plugin.parent.mkdir(parents=True, exist_ok=True)
    plugin.write_bytes((bundle / 'share/wsh/defaults' / reference).read_bytes() + (b'\n# user modification\n' if mode == 'modified' else b''))
    config = f'ZSH={shlex.quote(str(omz))}\nZSH_CUSTOM={shlex.quote(str(home / "custom"))}\nZSH_THEME=""\nplugins=(git zsh-autosuggestions)\nDISABLE_AUTO_UPDATE=true\nzstyle ":omz:update" mode disabled\nsource "$ZSH/oh-my-zsh.sh"\nPROMPT="OMZ> "\n'
    if mode == 'active':
        config += '_zsh_autosuggest_start\n'
    if mode == 'disabled':
        config += 'WSH_DISABLE_AUTOSUGGESTIONS=1\n'
    if mode == 'custom':
        config += '_zsh_autosuggest_strategy_probe() { suggestion="$1 CUSTOM"; }\nZSH_AUTOSUGGEST_STRATEGY=(probe)\nprobe-ready() { print -nr -- PROBE-READY; }\nzle -N probe-ready\nbindkey \'^T\' probe-ready\n'
    if mode == 'automatic':
        config += 'WSH_AUTOSUGGEST_REBIND_MODE=automatic\n'
    (home / '.zshrc').write_text(config)
    env = dict(PATH='/usr/bin:/bin', HOME=str(home), ZDOTDIR=str(home), TERM='xterm-256color', LC_ALL='C.UTF-8', WSH_THEME='')
    pid, fd = pty.fork()
    if not pid:
        os.chdir(home)
        os.execve(bundle / 'bin/wsh', ['wsh', '-di'], env)
    data = bytearray()
    def wait(marker, offset=0):
        end = time.monotonic() + 15
        while marker not in data[offset:]:
            assert time.monotonic() < end, bytes(data[-1500:])
            if select.select([fd], [], [], .05)[0]:
                data.extend(os.read(fd, 65536))
    try:
        wait(b'\x1b]133;B')
        offset = len(data)
        os.write(fd, b"print -r -- $'\\x1eOWNER:'\"$WSH_AUTOSUGGESTIONS_OWNER|$WSH_AUTOSUGGESTIONS_REPLACED|${+functions[compdef]}\"$'\\x1f'; print -r -- $'\\x1eDONE\\x1f'\n")
        wait(b'\x1eDONE\x1f', offset)
        start = data.index(b'\x1eOWNER:', offset) + 7
        state = bytes(data[start:data.index(b'\x1f', start)]).decode()
        expected = {'pending': 'wsh|1|1', 'automatic': 'wsh|1|1', 'active': 'external-active|0|1', 'modified': 'external-unknown|0|1', 'disabled': 'disabled|0|1', 'custom': 'wsh|1|1'}[mode]
        assert state == expected, (case, state)
        if mode in ('pending', 'automatic'):
            wait(b'\x1b]133;B', offset)
            offset = len(data)
            command = b"latewidget() { BUFFER+='LATE'; CURSOR=$#BUFFER; }; zle -N latewidget; "
            if mode == 'pending':
                command += b'_zsh_autosuggest_bind_widgets; '
            os.write(fd, command + b"print -r -- $'\\x1eBOUND\\x1f'\n")
            wait(b'\x1eBOUND\x1f', offset)
            wait(b'\x1b]133;B', offset)
            offset = len(data)
            os.write(fd, b"print -r -- $'\\x1eWIDGET:'$widgets[latewidget]$'\\x1f'\n")
            wait(b'\x1eWIDGET:user:_zsh_autosuggest_bound_', offset)
        if mode == 'custom':
            wait(b'\x1b]133;B', offset)
            offset = len(data)
            os.write(fd, b'echo probe')
            wait(b'CUSTOM', offset)
            # Wait for another editor callback after the asynchronous paint.
            os.write(fd, b'\x14')
            wait(b'PROBE-READY', offset)
            os.write(fd, b'\x03')
            wait(b'\x1b]133;B', offset)
        doctor = subprocess.run([bundle / 'bin/wsh', '--wsh-doctor'], env=env, capture_output=True, start_new_session=True, timeout=15)
        (home / 'doctor.txt').write_bytes(doctor.stdout + doctor.stderr)
        assert doctor.returncode == 0, doctor.stderr
        expected_advice = b'this external implementation is not verified by Wsh' if mode == 'modified' else b'no redundant or unrecognized external implementations detected' if mode == 'disabled' else b'an exact external copy is redundant'
        assert expected_advice in doctor.stdout, doctor.stdout
        rows.append(dict(case=case, state=state, doctor_status=doctor.returncode, passed=True))
    finally:
        (home / 'transcript.bin').write_bytes(data)
        os.kill(pid, signal.SIGHUP)
        os.waitpid(pid, 0)
        os.close(fd)
(output / 'results.json').write_text(json.dumps(rows, indent=2) + '\n')
print('PASS: real OMZ pending/active/modified/disabled/automatic ownership and completion coexistence')
