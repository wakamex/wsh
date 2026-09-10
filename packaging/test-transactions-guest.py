#!/usr/bin/env python3
"""Run actual RPM transactions while an old unprivileged native shell remains alive."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import select
import signal
import subprocess
import time

OUT = Path('/var/tmp/wsh-package-results')
OUT.mkdir(exist_ok=True)
results = []
account = pwd.getpwnam('shellempty')
def user():
    os.setsid()
    os.setgroups([])
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)

shell = subprocess.Popen(['/usr/bin/wsh', '-dfs'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, preexec_fn=user,
                         env={'HOME': account.pw_dir, 'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'})
transcript = bytearray()
def command(source, marker):
    shell.stdin.write(source.encode() + b'\n')
    shell.stdin.flush()
    output = bytearray()
    deadline = time.monotonic() + 10
    while marker not in output:
        assert time.monotonic() < deadline, bytes(output)
        if select.select([shell.stdout], [], [], .1)[0]:
            data = os.read(shell.stdout.fileno(), 65536)
            assert data, bytes(output)
            output.extend(data)
            transcript.extend(data)
    return bytes(output)

def rpm_path(release): return '/var/tmp/wsh-0.3.1-' + release + '.x86_64.rpm'
def run(name, argv, expected=None):
    result = subprocess.run(argv, capture_output=True, timeout=120)
    (OUT / (name + '.log')).write_bytes(result.stdout + result.stderr)
    if expected is not None: assert result.returncode == expected, (name, result)
    results.append({'case': name, 'command': argv, 'status': result.returncode})
    return result

try:
    command('print -r -- BEFORE:$ZSH_VERSION:$$', b'BEFORE:')
    before = os.stat('/proc/' + str(shell.pid) + '/exe').st_ino
    run('dnf-upgrade', ['dnf', '-y', 'upgrade', rpm_path('0.2')], 0)
    assert shell.poll() is None
    executable = os.readlink('/proc/' + str(shell.pid) + '/exe')
    assert executable.endswith(' (deleted)'), executable
    assert os.stat('/proc/' + str(shell.pid) + '/exe').st_ino == before
    output = command("zmodload zsh/zselect zsh/mathfunc; autoload -Uz colors; colors; print -r -- OLD_MODULES:$?:$((sin(1)))", b'OLD_MODULES:')
    assert b'OLD_MODULES:0:' in output, output
    output = command('''print -rl -- '{"type":"ping","version":1,"id":7}' '{"type":"shutdown","version":1,"id":8}' | /usr/libexec/wsh/bin/wsh-runtime serve --theme /usr/libexec/wsh/share/wsh/themes/minimal.toml; print -r -- OLD_RUNTIME:$?''', b'OLD_RUNTIME:')
    assert b'"type":"pong"' in output and b'OLD_RUNTIME:0' in output, output
    results.append({'case': 'old-shell-after-upgrade', 'pid': shell.pid, 'executable': executable, 'module_and_helper': True, 'same_zsh_abi': True})
    failed = run('rpm-pre-failure', ['rpm', '-Uvh', rpm_path('0.3')])
    assert failed.returncode != 0
    assert b'0.2' in run('version-after-pre-failure', ['rpm', '-q', 'wsh'], 0).stdout
    post = run('rpm-post-failure', ['rpm', '-Uvh', rpm_path('0.4')])
    assert b'injected post-install failure' in post.stderr
    assert b'0.4' in run('version-after-post-failure', ['rpm', '-q', 'wsh'], 0).stdout
    run('new-shell-after-post-failure', ['runuser', '-u', 'shellempty', '--', '/usr/bin/wsh', '-fc', 'print -r -- USABLE'], 0)
    run('dnf-downgrade', ['dnf', '-y', 'downgrade', rpm_path('0.1')], 0)
    pause_log = open(OUT / 'rpm-interrupted.log', 'wb')
    transaction = subprocess.Popen(['rpm', '-Uvh', rpm_path('0.5')], stdout=pause_log, stderr=subprocess.STDOUT, start_new_session=True)
    deadline = time.monotonic() + 30
    while not Path('/run/wsh-rpm-post-paused').exists():
        assert transaction.poll() is None and time.monotonic() < deadline
        time.sleep(.05)
    os.killpg(transaction.pid, signal.SIGKILL)
    status = transaction.wait(timeout=5)
    pause_log.close()
    results.append({'case': 'interrupted-after-payload-install', 'status': status, 'phase': 'post-scriptlet', 'power_loss_during_payload': False})
    run('new-shell-after-interruption', ['runuser', '-u', 'shellempty', '--', '/usr/bin/wsh', '-fc', 'print -r -- USABLE'], 0)
    run('rpm-query-after-interruption', ['rpm', '-q', 'wsh'])
    run('repair-interrupted-transaction', ['rpm', '-Uvh', '--oldpackage', '--replacepkgs', rpm_path('0.2')], 0)
    run('verify-repaired-package', ['rpm', '-V', 'wsh'], 0)
    command('print -r -- OLD_STILL_ALIVE:$ZSH_VERSION', b'OLD_STILL_ALIVE:')
    shell.stdin.write(b'exit 23\n'); shell.stdin.flush()
    assert shell.wait(timeout=5) == 23
    (OUT / 'transactions.json').write_text(json.dumps(results, indent=2) + '\n')
    print('PASS: real upgrade, failure, interruption, downgrade and old-shell resource operations')
finally:
    if shell.poll() is None:
        os.killpg(shell.pid, signal.SIGKILL)
        shell.wait()
    (OUT / 'old-shell.bin').write_bytes(transcript)
