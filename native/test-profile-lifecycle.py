#!/usr/bin/env python3
"""Real native startup, interruption and saved-profile recovery contracts."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

BUNDLE = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve(); OUT.mkdir(parents=True, exist_ok=True)
BINARY = BUNDLE / 'bin/wsh'
results = []

def run(name, files, flags, status, present, absent=(), delays=(), binary=BINARY):
    case = OUT / name; case.mkdir()
    home = case / 'home'; home.mkdir()
    for file, text in files.items(): (home / file).write_text(text)
    env = {'HOME': str(home), 'ZDOTDIR': str(home), 'WSH_STATE_ROOT': str(case / 'state'), 'PATH': '/usr/bin:/bin', 'TERM': 'xterm-256color', 'LC_ALL': 'C.UTF-8'}
    env.update({key: os.environ[key] for key in ['ASAN_OPTIONS', 'UBSAN_OPTIONS'] if key in os.environ})
    before = {p.name: p.read_bytes() for p in home.iterdir()}
    process = subprocess.run([binary, '--wsh-profile', '--', *flags], env=env, capture_output=True, timeout=8)
    (case / 'stdout').write_bytes(process.stdout); (case / 'stderr').write_bytes(process.stderr)
    assert process.returncode == status, (name, process)
    profile = next((case / 'state/profiles').iterdir())
    events = [json.loads(line) for line in (profile / 'trace.jsonl').read_bytes().splitlines()]
    names = [e['event'] for e in events]
    for event in present: assert names.count(event) == 1, (name, event, names)
    for event in absent: assert event not in names, (name, event, names)
    for start, end, minimum in delays:
        a = next(e['elapsed_us'] for e in events if e['event'] == start)
        b = next(e['elapsed_us'] for e in events if e['event'] == end)
        assert b - a >= minimum, (name, start, end, b - a)
    report = subprocess.run([BINARY, '--wsh-profile-report', profile], capture_output=True, timeout=3)
    assert report.returncode == 0, (name, report)
    (case / 'report.txt').write_bytes(report.stdout)
    assert before == {p.name: p.read_bytes() for p in home.iterdir() if p.name in before}
    results.append({'case': name, 'status': status, 'events': names, 'recovery_status': report.returncode})

base = {'.zshenv': 'unsetopt globalrcs\nsleep 0.025\n'}
startup = ['native-startup-enter', 'user-zshenv-start', 'user-zshenv-end']
delay = [('user-zshenv-start', 'user-zshenv-end', 20000)]
run('noninteractive', base, ['-dc', 'exit 19'], 19, startup, delays=delay)
run('early-zshenv', {'.zshenv': base['.zshenv'] + 'exit 23\n'}, ['-di'], 23, ['native-startup-enter', 'user-zshenv-start'], ['user-zshenv-end'])
run('early-zprofile', dict(base, **{'.zprofile': 'sleep 0.025\nexit 31\n'}), ['-dlc', 'exit 1'], 31, startup + ['user-zprofile-start'], ['user-zprofile-end'], delay)
run('early-zshrc', dict(base, **{'.zshrc': 'sleep 0.025\nexit 37\n'}), ['-dic', 'exit 1'], 37, startup + ['user-zshrc-start'], ['user-zshrc-end'], delay)
run('login', dict(base, **{'.zprofile': 'sleep 0.025\n', '.zlogin': 'sleep 0.025\n'}), ['-dlc', 'exit 29'], 29, startup + ['user-zprofile-start', 'user-zprofile-end', 'user-zlogin-start', 'user-zlogin-end'], delays=delay + [('user-zprofile-start', 'user-zprofile-end', 20000), ('user-zlogin-start', 'user-zlogin-end', 20000)])
run('subshell', {'.zshenv': base['.zshenv'] + '(exit 7)\n'}, ['-dc', '(exit 11); exit 13'], 13, startup, delays=delay)
run('exec-recovery', base, ['-dc', 'exec /bin/sh -c "exit 29"'], 29, startup, delays=delay)
run('sigkill-recovery', base, ['-dc', 'kill -KILL $$'], -9, startup, delays=delay)
run('sigterm-recovery', base, ['-dc', 'kill -TERM $$'], -15, startup, delays=delay)
run('no-rcs', base, ['-dfc', 'exit 17'], 17, ['native-startup-enter'], ['user-zshenv-start'])
# A relocated bare executable lacks Wsh integration.
missing = OUT / 'bare-installation/bin'; missing.mkdir(parents=True)
shutil.copy2(BINARY, missing / 'wsh')
run('missing-integration', base, ['-dc', 'exit 19'], 19, startup, delays=delay, binary=missing / 'wsh')
(OUT / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
print('PASS: 11 native startup attribution, early exit, subshell, exec, signal and missing-integration recovery cases')
