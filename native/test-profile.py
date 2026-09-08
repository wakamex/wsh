#!/usr/bin/env python3
"""Native profiling attribution, recovery, privacy, exact arguments and status."""
import hashlib
import json
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import time

BUNDLE = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve(); OUT.mkdir(parents=True, exist_ok=True)
BINARY = BUNDLE / 'bin/wsh'
READY = b'\x1b]133;B'
results = []
home = OUT / 'home'; home.mkdir(exist_ok=True)
state = OUT / 'state'; state.mkdir(exist_ok=True, mode=0o700)
repo = OUT / 'repository-private-path'; repo.mkdir(exist_ok=True)
def git(*args): subprocess.run(['git', '-C', repo, *args], check=True, capture_output=True)
git('init', '-q', '-b', 'main'); git('config', 'user.name', 'profile-test'); git('config', 'user.email', 'profile@wsh.invalid')
(repo / 'tracked').write_text('seed\n'); git('add', 'tracked'); git('commit', '-qm', 'seed')
(home / '.zshenv').write_text('unsetopt globalrcs\nWSH_SECRET=never-record-this-secret\nsleep 0.05\n')
(home / '.zshrc').write_text('''PROMPT="NATIVE> "
WSH_THEME=minimal
ZSHZ_DATA=$HOME/jump-data
wsh_profile_slow() { sleep 0.02; }
wsh_profile_slow
zmodload zsh/zle
autoload -Uz add-zle-hook-widget
wsh_profile_editor_delay() { sleep 0.08; }
add-zle-hook-widget zle-line-init wsh_profile_editor_delay
''')
before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in home.glob('.zsh*')}
env = {'HOME': str(home), 'ZDOTDIR': str(home), 'WSH_STATE_ROOT': str(state), 'PATH': '/usr/bin:/bin', 'TERM': 'xterm-256color', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC'}
env.update({name: os.environ[name] for name in ('ASAN_OPTIONS', 'UBSAN_OPTIONS') if name in os.environ})
pid, fd = pty.fork()
if not pid:
    os.chdir(repo)
    os.execve(BINARY, [str(BINARY), '--wsh-profile', '--functions', '--', '-d', '-i'], env)
transcript = bytearray()
def wait(marker, timeout=8):
    output = bytearray(); deadline = time.monotonic() + timeout
    while marker not in output:
        assert time.monotonic() < deadline, bytes(output)
        if select.select([fd], [], [], .05)[0]:
            data = os.read(fd, 65536); output.extend(data); transcript.extend(data)
    return bytes(output)
try:
    wait(READY)
    profiles = list((state / 'profiles').iterdir()); assert len(profiles) == 1
    profile = profiles[0]
    assert os.readlink('/proc/' + str(pid) + '/exe') == str(BINARY)
    deadline = time.monotonic() + 5
    while True:
        r = subprocess.run([BINARY, '--wsh-profile-report', profile], env=env, capture_output=True, timeout=3)
        if r.returncode == 0 and b'Child processes: 1' in r.stdout and b'Theme: minimal' in r.stdout: break
        assert time.monotonic() < deadline, (r.stdout, r.stderr)
        time.sleep(.03)
    (OUT / 'live-report.txt').write_bytes(r.stdout)
    assert b'wsh_profile_slow' in r.stdout
    events = [json.loads(line) for line in (profile / 'trace.jsonl').read_text().splitlines()]
    event_map = {e['event']: e for e in events}
    assert event_map['user-zshenv-end']['elapsed_us'] - event_map['user-zshenv-start']['elapsed_us'] >= 40000
    assert event_map['user-zshrc-end']['elapsed_us'] - event_map['user-zshrc-start']['elapsed_us'] >= 15000
    assert event_map['editor-ready']['elapsed_us'] - event_map['user-zshrc-end']['elapsed_us'] >= 70000
    os.write(fd, b'print -r -- PROFILE_STATUS:$?; exit 23\n')
    wait(b'Wsh profile')
    while True:
        ended, status = os.waitpid(pid, os.WNOHANG)
        if ended:
            assert os.waitstatus_to_exitcode(status) == 23
            pid = None
            break
        if select.select([fd], [], [], .05)[0]:
            try: transcript.extend(os.read(fd, 65536))
            except OSError: pass
    for name in ('metadata.json', 'trace.jsonl', 'zprof.txt'):
        p = profile / name; assert p.stat().st_mode & 0o777 == 0o600
    assert profile.stat().st_mode & 0o777 == 0o700
    trace = (profile / 'trace.jsonl').read_bytes()
    assert b'never-record-this-secret' not in trace and os.fsencode(repo) not in trace
    assert b'"command"' not in trace and b'"cwd"' not in trace and b'"prompt"' not in trace
    results.append({'case': 'interactive native attribution and live report', 'status': 23, 'private': True, 'path': str(profile)})
finally:
    if pid is not None:
        os.killpg(pid, signal.SIGHUP); os.waitpid(pid, 0)
    os.close(fd)
    (OUT / 'interactive.bin').write_bytes(transcript)
assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in home.glob('.zsh*')}
for flags in (['-fc', 'exit 7'], ['-dc', 'exit 9'], ['-dlc', 'exit 11'], ['-dfc', 'print -r -- ${(qqq)1}; exit 13', 'profile-argv', b'\xff\n$(false)']):
    r = subprocess.run([BINARY, '--wsh-profile', '--', *flags], env=env, capture_output=True, timeout=5)
    expected = (7, 9, 11, 13)[len(results) - 1]
    assert r.returncode == expected and b'Wsh profile' in r.stdout, (flags, r)
    if expected == 13:
        plain = subprocess.run([BINARY, *flags], env=env, capture_output=True, timeout=5)
        assert plain.returncode == 13 and plain.stdout and r.stdout.startswith(plain.stdout), (plain, r)
    results.append({'case': 'exact Zsh arguments ' + str(flags[:-1]), 'status': r.returncode})
for flags in (['--bad'], ['--functions', '--functions'], ['-ic', 'exit'], [b'\xff']):
    r = subprocess.run([BINARY, '--wsh-profile', *flags], env=env, capture_output=True, timeout=3)
    assert r.returncode == 2 and b'usage:' in r.stderr
    results.append({'case': 'malformed profile invocation', 'status': 2})
count = len(list((state / 'profiles').iterdir()))
r = subprocess.run([BINARY, '-dfc', 'exit 17'], env=env, capture_output=True, timeout=3)
assert r.returncode == 17 and len(list((state / 'profiles').iterdir())) == count
results.append({'case': 'ordinary shell creates no profile', 'status': 17})
(OUT / 'profile-results.json').write_text(json.dumps(results, indent=2) + '\n')
print('PASS: native profile attribution, runtime, functions, recovery, privacy, argv and status')
