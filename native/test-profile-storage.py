#!/usr/bin/env python3
"""Profile storage boundaries and native command-status parity."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

BINARY = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve(); OUT.mkdir(parents=True, exist_ok=True)
results = []
with tempfile.TemporaryDirectory(prefix='wsh-profile-storage-') as directory:
    root = Path(directory); home = root / 'home'; home.mkdir()
    env = {'HOME': str(home), 'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8'}
    env.update({key: os.environ[key] for key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS') if key in os.environ})
    def check(name, overrides, expected, command='exit 7'):
        environment = dict(env, **overrides)
        r = subprocess.run([BINARY, '--wsh-profile', '--', '-dfc', command], cwd=root, env=environment, capture_output=True, timeout=5)
        passed = r.returncode == expected
        results.append({'case': name, 'status': r.returncode, 'expected': expected, 'passed': passed})
        (OUT / (name + '.out')).write_bytes(r.stdout + r.stderr)
        return r
    check('relative-state-root', {'WSH_STATE_ROOT': 'relative-state'}, 7)
    parent = root / 'public-parent'; parent.mkdir(mode=0o755)
    parent.chmod(0o755)
    check('existing-parent-preserved', {'WSH_STATE_ROOT': str(parent)}, 7)
    assert parent.stat().st_mode & 0o777 == 0o755
    (parent / 'profiles').chmod(0o755)
    check('public-profiles-rejected', {'WSH_STATE_ROOT': str(parent)}, 1)
    assert (parent / 'profiles').stat().st_mode & 0o777 == 0o755
    symlink_state = root / 'symlink-state'; symlink_state.mkdir()
    target = root / 'symlink-target'; target.mkdir(mode=0o700)
    (symlink_state / 'profiles').symlink_to(target)
    check('symlink-profiles-rejected', {'WSH_STATE_ROOT': str(symlink_state)}, 1)
    assert not list(target.iterdir())
    blocked = root / 'file-state'; blocked.write_text('leave this file alone')
    check('file-state-rejected', {'WSH_STATE_ROOT': str(blocked)}, 1)
    assert blocked.read_text() == 'leave this file alone'
    check('missing-home-rejected', {'HOME': ''}, 1)
    check('unwritable-state-rejected', {'WSH_STATE_ROOT': '/proc/wsh-profile-no-write'}, 1)
    for command in ('exit 19', 'kill -TERM $$'):
        plain = subprocess.run([BINARY, '-dfc', command], env=env, capture_output=True, timeout=5)
        check('command-' + ('term' if 'TERM' in command else 'exit'), {'WSH_STATE_ROOT': str(root / 'status-state')}, plain.returncode, command)
(OUT / 'storage-results.json').write_text(json.dumps(results, indent=2) + '\n')
assert all(row['passed'] for row in results), results
print('PASS: private storage, parent preservation, native exit and signal status')
