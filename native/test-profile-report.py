#!/usr/bin/env python3
"""Adversarial saved-report checks against the compiled C/Jansson reader."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

BINARY = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve(); OUT.mkdir(parents=True, exist_ok=True)
arguments = ['--wsh-profile-report'] if len(sys.argv) > 3 else []
digest = 'a' * 64
metadata = {'schema_version': 2, 'wsh_version': '0.3.1', 'source_revision': 'c4ac10f', 'native_inputs_sha256': digest,
            'zsh_version': '5.9.999.3-test', 'zsh_source_revision': 'cad0d67c', 'target': 'x86_64-linux-gnu'}
launch = {'schema_version': 1, 'source': 'manager', 'event': 'launch-ready', 'elapsed_us': 2, 'wsh_version': '0.3.1', 'bundle_sha256': digest}
events = [launch, {'schema_version': 1, 'source': 'zsh', 'event': 'user-zshrc-start', 'elapsed_us': 100},
          {'schema_version': 1, 'source': 'zsh', 'event': 'user-zshrc-end', 'elapsed_us': 10200}]
results = []
with tempfile.TemporaryDirectory(prefix='wsh-profile-reader-') as directory:
    root = Path(directory); profile = root / 'profile'; profile.mkdir(mode=0o700)
    def write(name, content):
        p = profile / name
        if p.exists() or p.is_symlink(): p.unlink()
        p.write_bytes(content if isinstance(content, bytes) else content.encode())
        p.chmod(0o600)
    def reset():
        write('metadata.json', json.dumps(metadata) + '\n')
        write('trace.jsonl', ''.join(json.dumps(e) + '\n' for e in events))
        write('zprof.txt', 'num  calls time self name\n-----------------------------------\n 1) 2 3.00 1.50 75.00% 2.50 1.25 62.50% slow\n 2) 1 1.00 1.00 25.00% 1.00 1.00 25.00% fast\n\n')
        profile.chmod(0o700)
    def check(name, passed, path=profile):
        r = subprocess.run([BINARY, *arguments, path], capture_output=True, timeout=3)
        assert (r.returncode == 0) == passed, (name, r.returncode, r.stdout, r.stderr)
        assert b'AddressSanitizer' not in r.stderr and b'runtime error:' not in r.stderr, (name, r.stderr)
        results.append({'case': name, 'status': r.returncode, 'accepted': passed})
        return r
    reset()
    r = check('native saved report', True)
    assert b'User .zshrc: 10.100 ms' in r.stdout and b'2.500 ms  slow' in r.stdout
    (OUT / 'native-synthetic-report.txt').write_bytes(r.stdout)
    write('metadata.json', json.dumps({'schema_version': 1, 'bundle_root': '/nonexistent/deleted-bundle', 'bundle_sha256': digest}))
    r = check('legacy recovery without installed bundle', True)
    assert b'recorded legacy identity' in r.stdout and b'User .zshrc: 10.100 ms' in r.stdout
    for key, value in [('schema_version', 3), ('schema_version', 4294967298), ('target', 'evil\x1b]52;clipboard'), ('native_inputs_sha256', 'b' * 64), ('unknown', 1), ('source|event', 'x')]:
        reset(); changed = dict(metadata); changed[key] = value
        write('metadata.json', json.dumps(changed))
        check('metadata rejected ' + key + ':' + str(value), False)
    reset(); write('metadata.json', json.dumps(metadata)[:-1] + ',"schema_version":2}')
    check('duplicate metadata key', False)
    for field, value in [('schema_version', 2), ('source', 'other'), ('event', 'bad\nvalue'), ('elapsed_us', -1), ('elapsed_us', None), ('elapsed_us', 1.5), ('duration_us', -1), ('prompt_changed', 1), ('theme', 'bad\x1b'), ('unknown', 'value'), ('source|event', 'x')]:
        reset(); changed = dict(launch); changed[field] = value
        write('trace.jsonl', json.dumps(changed) + '\n')
        check('event rejected ' + field + ':' + str(value), False)
    reset(); write('trace.jsonl', json.dumps(launch)[:-1] + ',"elapsed_us":3}\n')
    check('duplicate event key', False)
    for name, data in [('truncated', b'{'), ('invalid UTF-8', b'{"event":"\xff"}\n'), ('NUL', b'{}\x00\n'), ('oversized line', b' ' * 65536 + b'\n'), ('deep object', b'{"x":' * 3000 + b'0' + b'}' * 3000 + b'\n')]:
        reset(); write('trace.jsonl', data); check(name, False)
    reset(); changed = dict(launch, duration_us=None, prompt_changed=None)
    write('trace.jsonl', json.dumps(changed) + '\n'); check('optional null fields', True)
    for name in ('metadata.json', 'trace.jsonl', 'zprof.txt'):
        reset(); target = root / ('target-' + name); target.write_bytes((profile / name).read_bytes()); target.chmod(0o600)
        (profile / name).unlink(); (profile / name).symlink_to(target)
        check('symlink ' + name, False)
        reset(); (profile / name).chmod(0o644); check('public ' + name, False)
        reset(); (profile / name).unlink(); os.mkfifo(profile / name, 0o600); check('FIFO ' + name, False)
    reset(); profile.chmod(0o755); check('public directory', False)
    reset(); link = root / 'link'; link.symlink_to(profile); check('symlink directory', False, link)
    reset(); write('trace.jsonl', b' ' * (8 * 1024 * 1024 + 1)); check('trace limit', False)
    reset(); write('zprof.txt', b' ' * (1024 * 1024 + 1)); check('function limit', False)
    reset(); write('metadata.json', b' ' * 4097); check('metadata limit', False)
    reset(); (profile / 'zprof.txt').unlink(); check('optional function file absent', True)
    reset(); write('zprof.txt', b'header\n-----\n1) 1 0.0 0.0 0% 1.0 1.0 1% bad\xff\n')
    check('invalid UTF-8 function profile rejected', False)
    reset(); text = (profile / 'zprof.txt').read_text().replace('slow', 'bad\x1b[31m')
    write('zprof.txt', text); r = check('function terminal controls escaped', True)
    assert b'\x1b' not in r.stdout and b'bad\\x1b[31m' in r.stdout
    reset(); text = (profile / 'zprof.txt').read_text().replace('2.50', '1e9999')
    write('zprof.txt', text); r = check('overflowing function time omitted', True)
    assert b'ms  slow' not in r.stdout
(OUT / 'report-cases.json').write_text(json.dumps(results, indent=2) + '\n')
print('PASS:', len(results), 'saved-profile reader boundaries')
