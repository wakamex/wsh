#!/usr/bin/env python3
"""Verify an unprivileged account can select the registered native shell through PAM."""
import os
from pathlib import Path
import pty
import pwd
import select
import signal
import subprocess
import time

account = pwd.getpwnam('shellempty')
subprocess.run(['chsh', '-s', '/bin/bash', account.pw_name], check=True)
pid, fd = pty.fork()
if not pid:
    os.setgroups([])
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
    os.execve('/usr/bin/chsh', ['chsh', '-s', '/usr/bin/wsh'], {'HOME': account.pw_dir, 'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
output = bytearray()
try:
    deadline = time.monotonic() + 15
    while b'Password:' not in output:
        assert time.monotonic() < deadline, bytes(output)
        if select.select([fd], [], [], .1)[0]: output.extend(os.read(fd, 65536))
    os.write(fd, b'wsh-regression\n')
    while True:
        ended, status = os.waitpid(pid, os.WNOHANG)
        if ended:
            assert os.waitstatus_to_exitcode(status) == 0, bytes(output)
            pid = None
            break
        assert time.monotonic() < deadline, bytes(output)
        if select.select([fd], [], [], .1)[0]:
            try: output.extend(os.read(fd, 65536))
            except OSError: pass
    assert pwd.getpwnam('shellempty').pw_shell == '/usr/bin/wsh'
    print('PASS: unprivileged chsh authenticates and selects registered /usr/bin/wsh')
finally:
    if pid is not None:
        os.killpg(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    os.close(fd)
    Path('/var/tmp/wsh-package-results/chsh.bin').write_bytes(output)
