#!/usr/bin/env python3
"""Run a script through the disposable VM's independent recovery account."""
import os
from pathlib import Path
import subprocess
import sys

WORK = Path(os.environ.get('WSH_VM_WORK', '/var/tmp/wsh-native-vm'))
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', '-o', 'UserKnownHostsFile=' + str(WORK / 'known_hosts'),
       '-i', str(WORK / 'id_ed25519'), '-p', '22284', 'recovery@127.0.0.1']

def run(script, name, expected=0):
    (WORK / (name + '.sh')).write_text(script)
    result = subprocess.run(SSH + ['sudo -n /bin/bash -s'], input=script.encode(), capture_output=True, timeout=180)
    (WORK / (name + '.log')).write_bytes(result.stdout + result.stderr)
    if expected is not None:
        assert result.returncode == expected, (name, result.returncode, result.stdout, result.stderr)
    return result

if __name__ == '__main__':
    result = run(sys.stdin.read(), sys.argv[1], expected=None)
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    raise SystemExit(result.returncode)
