#!/usr/bin/env python3
"""Exercise real serial getty/PAM login in the disposable Fedora guest."""
import json
import os
from pathlib import Path
import select
import socket
import sys
import time

WORK = Path(os.environ.get('WSH_VM_WORK', '/var/tmp/wsh-native-vm'))
name = sys.argv[1]
account = sys.argv[2] if len(sys.argv) > 2 else 'shelltest'
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect(str(WORK / 'serial.sock'))
transcript = bytearray()

def wait(marker, timeout=30):
    output = bytearray()
    deadline = time.monotonic() + timeout
    while marker not in output:
        assert time.monotonic() < deadline, (marker, bytes(output))
        if select.select([sock], [], [], .1)[0]:
            chunk = sock.recv(65536)
            assert chunk, 'serial connection closed'
            output.extend(chunk)
            transcript.extend(chunk)
    return bytes(output)

try:
    sock.sendall(b'\n')
    wait(b'login:')
    sock.sendall(account.encode() + b'\n')
    wait(b'Password:')
    sock.sendall(b'wsh-regression\n')
    wait(b'\x1b]133;B')
    sock.sendall(b'print -r -- VM_LOGIN:$ZSH_VERSION:$SHELL:$ZSH_EXEPATH; id; print -r -- VM_DONE\n')
    output = wait(b'VM_DONE\r\n')
    assert b'VM_LOGIN:5.9.999.3-test:/usr/bin/wsh:/usr/libexec/wsh/bin/wsh' in output, output
    assert b'uid=' in output and account.encode() in output, output
    if '--job-control' in sys.argv:
        sock.sendall(b'''python3 -c 'import signal,time; signal.signal(signal.SIGCONT,lambda *a:print("CHILD_"+"RESUMED",flush=True)); print("CHILD_"+"READY",flush=True); time.sleep(30)'\n''')
        wait(b'CHILD_READY')
        sock.sendall(b'\x1a')
        wait(b'suspended')
        sock.sendall(b'fg\n')
        wait(b'CHILD_RESUMED')
        sock.sendall(b'\x03')
        wait(b'\x1b]133;D')
        sock.sendall(b'print -r -- JOB_STATUS:$?\n')
        wait(b'JOB_STATUS:130')
    sock.sendall(b'exit\n')
    wait(b'login:')
    (WORK / (name + '.json')).write_text(json.dumps({'account': account, 'pam_tty_login': True, 'native_version': '5.9.999.3-test', 'job_control': '--job-control' in sys.argv}, indent=2) + '\n')
    print('PASS: real serial getty/PAM native login', name, account)
finally:
    (WORK / (name + '.bin')).write_bytes(transcript)
    sock.close()
