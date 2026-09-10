#!/usr/bin/env python3
"""Compare whole-database confirmation against pinned Zsh-z in a controlling PTY."""
import errno
import json
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import time

binary, module, fixture, out = [Path(p).resolve() for p in sys.argv[1:5]]
baseline = '--baseline' in sys.argv[5:]
out.mkdir(parents=True, exist_ok=True)
home = out/'home'
home.mkdir(exist_ok=True)
data = home/'db'
initial = b'/one|2|1700000000\n/two|3|1700000000\n'
script = out/'run.zsh'
script.write_text('''module_path=($1 $module_path)
(( $+builtins[wsh-directory] )) || zmodload wshdirectory || exit 90
source "$2"
zshz -xR /
exit $?
''')
env = dict(os.environ, HOME=str(home), ZSHZ_DATA=str(data), LC_ALL='C.UTF-8')
rows = []
for owner in ('control', 'candidate'):
    for action, answer in [('yes', b'y'), ('no', b'n'), ('interrupt', b'\x03')]:
        data.write_bytes(initial)
        pid, master = pty.fork()
        if pid == 0:
            os.execve(binary, [str(binary), '-df', str(script), str(module), str(fixture/(owner+'.zsh'))], env)
        transcript = bytearray()
        prompted = False
        lock_status = None
        status = None
        deadline = time.monotonic()+5
        try:
            while time.monotonic() < deadline:
                readable, _, _ = select.select([master], [], [], .05)
                if readable:
                    try:
                        chunk = os.read(master, 8192)
                    except OSError as exc:
                        if exc.errno != errno.EIO:
                            raise
                        break
                    if not chunk:
                        break
                    transcript.extend(chunk)
                if not prompted and b'Delete entire Zsh-z database? ' in transcript:
                    prompted = True
                    assert data.read_bytes() == initial
                    lock = home/'db.lock'
                    lock.touch()
                    probe = subprocess.run([binary, '-dfc', 'zmodload zsh/system; zsystem flock -t 0.1 -f fd "$1"', 'lock', lock], env=env, capture_output=True, timeout=2)
                    lock_status = probe.returncode
                    assert lock_status == 0, probe.stderr
                    os.write(master, answer)
            else:
                raise AssertionError('confirmation timed out')
        finally:
            os.close(master)
            waited, status = os.waitpid(pid, os.WNOHANG)
            if not waited:
                # A closed controlling terminal also bounds unexpected shell waits.
                os.kill(pid, signal.SIGHUP)
                _, status = os.waitpid(pid, 0)
        row = dict(owner=owner, action=action, prompted=prompted, lock_status=lock_status, status=os.waitstatus_to_exitcode(status), transcript=transcript.hex(), database=data.read_bytes().hex())
        rows.append(row)
        (out/'results.json').write_text(json.dumps(rows, indent=2)+'\n')
        if not baseline or owner == 'control':
            assert prompted, row
            assert data.read_bytes() == (b'\n' if action == 'yes' else initial), row
            if action != 'interrupt':
                assert row['status'] == (0 if action == 'yes' else 1), row
print(json.dumps(rows, indent=2))
# With no controlling terminal, redirected input must not approve deletion.
for owner in ('control', 'candidate'):
    data.write_bytes(initial)
    result = subprocess.run([binary, '-df', script, module, fixture/(owner+'.zsh')], env=env, input=b'y\n', capture_output=True, start_new_session=True, timeout=5)
    assert result.returncode != 0 and data.read_bytes() == initial
    rows.append(dict(owner=owner, action='no-tty', status=result.returncode, stdout=result.stdout.hex(), stderr=result.stderr.hex(), database=data.read_bytes().hex()))
(out/'results.json').write_text(json.dumps(rows, indent=2)+'\n')
