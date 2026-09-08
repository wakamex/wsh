#!/usr/bin/env python3
"""Native profiles do not collect child-shell events through inherited settings."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

BUNDLE = Path(sys.argv[1]).resolve(); BINARY = BUNDLE / 'bin/wsh'
OUT = Path(sys.argv[2]).resolve(); OUT.mkdir(parents=True, exist_ok=True)
results = []
base = 'unsetopt globalrcs\n'
for name, startup, flags in [
    ('command-child', base, ['-dc', '"$WSH_TEST_BINARY" -dic "exit 3"; [[ $? == 3 ]] || exit 97; exit 19']),
    ('startup-child', base + 'if [[ -z ${WSH_CHILD_TEST-} ]]; then WSH_CHILD_TEST=1 "$WSH_TEST_BINARY" -dic "exit 3"; [[ $? == 3 ]] || exit 97; fi\n', ['-dc', 'exit 19']),
    ('no-rcs-environment', base, ['-dfc', '/usr/bin/env > "$HOME/child-env"; exit 19']),
    ('ordinary-environment', base, ['-dc', '/usr/bin/env > "$HOME/child-env"; exit 19']),
    ('sh-emulation-environment', base, ['--emulate', 'sh', '-c', '/usr/bin/env > "$HOME/child-env"; exit 19']),
    ('explicit-child-profile', base, ['-dc', '"$WSH_TEST_BINARY" --wsh-profile -- -dc "exit 3"; [[ $? == 3 ]] || exit 97; exit 19']),
    ('missing-integration-environment', base, ['-dc', '/usr/bin/env > "$HOME/child-env"; exit 19']),
]:
    case = OUT / name; case.mkdir(); home = case / 'home'; home.mkdir()
    (home / '.zshenv').write_text(startup)
    (home / '.zshrc').write_text('PROMPT="CHILD> "\nWSH_THEME=\nZSHZ_DATA=$HOME/jump-data\n')
    env = {'HOME': str(home), 'ZDOTDIR': str(home), 'WSH_STATE_ROOT': str(case / 'state'), 'WSH_TEST_BINARY': str(BINARY), 'PATH': '/usr/bin:/bin', 'TERM': 'xterm-256color', 'LC_ALL': 'C.UTF-8'}
    env.update({key: os.environ[key] for key in ['ASAN_OPTIONS', 'UBSAN_OPTIONS'] if key in os.environ})
    binary = BINARY
    if name.startswith('missing-integration'):
        binary = case / 'bare/bin/wsh'; binary.parent.mkdir(parents=True); shutil.copy2(BINARY, binary)
    r = subprocess.run([binary, '--wsh-profile', '--', *flags], env=env, capture_output=True, timeout=10)
    (case / 'stdout').write_bytes(r.stdout); (case / 'stderr').write_bytes(r.stderr)
    assert r.returncode == 19, (name, r)
    profiles = list((case / 'state/profiles').iterdir())
    assert len(profiles) == (2 if name == 'explicit-child-profile' else 1), (name, profiles)
    for profile in profiles:
        events = [json.loads(line)['event'] for line in (profile / 'trace.jsonl').read_bytes().splitlines()]
        assert events.count('launch-ready') == 1 and events.count('native-startup-enter') == 1, (name, events)
        assert 'directory-jump-start' not in events and 'shell-exit' not in events, (name, events)
    exported = []
    if (home / 'child-env').exists():
        exported = [line.split(b'=', 1)[0].decode() for line in (home / 'child-env').read_bytes().splitlines() if line.startswith((b'WSH_PROFILE_', b'WSH_TRACE_FILE='))]
        assert not exported, (name, exported)
    results.append({'case': name, 'status': r.returncode, 'profiles': len(profiles), 'inherited_profile_variables': exported})
(OUT / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
print('PASS: seven native child-shell, explicit child profile and environment isolation cases')
