#!/usr/bin/env python3
"""Compare real Rust/C TOML validators on definitions and deterministic mutations."""
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUST, NATIVE, OUT = [Path(p).resolve() for p in sys.argv[1:]]
OUT.mkdir(parents=True)
environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=1', UBSAN_OPTIONS='halt_on_error=1', LC_ALL='C.UTF-8')
base = (ROOT / 'themes/minimal.toml').read_bytes()
cases = []
def add(name, source): cases.append((name, source))
for path in sorted((ROOT / 'themes').glob('*.toml')): add('shipped-' + path.stem, path.read_bytes())
lines = base.splitlines(keepends=True)
for index, line in enumerate(lines):
    if b'=' not in line or line.lstrip().startswith(b'#'): continue
    key = line.split(b'=', 1)[0]
    add('missing-field-' + str(index), b''.join(lines[:index] + lines[index+1:]))
    add('duplicate-field-' + str(index), b''.join(lines[:index] + [line] + lines[index:]))
    for value in [b'true', b'0', b'-1', b'1.0', b'"value"', b'[]', b'{}', b'"\\u0000"']:
        add('field-type-' + str(index) + '-' + value.hex(), b''.join(lines[:index] + [key + b'= ' + value + b'\n'] + lines[index+1:]))
for index, line in enumerate(lines):
    if line.startswith(b'['): add('unknown-nested-' + str(index), b''.join(lines[:index+1] + [b'unknown-field = 1\n'] + lines[index+1:]))
add('unknown-root', b'unknown = 1\n' + base)
add('unknown-empty-table', base + b'\n[unknown]\n')
add('unknown-empty-nested-table', base + b'\n[cwd.unknown]\n')
add('quoted-dot-key', b'"git.prefix" = "x"\n' + base)
add('nul-key', b'"id\\u0000ignored" = "x"\n' + base)
add('utf8-bom', b'\xef\xbb\xbf' + base)
add('crlf', base.replace(b'\n', b'\r\n'))
add('comments', b'# Unicode comment: \xce\xb1\n' + base)
for value in ['0', '-0', '-1', '+1', str(2**63-1), str(2**63), str(2**64-1), str(2**64), '+18446744073709551615', '18_446_744_073_709_551_615', '0xffffffffffffffff', '0b'+'1'*64, '0o1777777777777777777777', '0b'+'0'*100+'1', '0b'+'1'*65, '01', '1_', '--1', '++1']:
    add('duration-number-' + value, base.replace(b'threshold-ms = 2000', b'threshold-ms = ' + value.encode()))
for length in [0, 1, 64, 65, 128, 129, 4096]:
    add('id-length-' + str(length), base.replace(b'id = "minimal"', b'id = "' + b'a'*length + b'"'))
    add('unicode-name-length-' + str(length), base.replace(b'name = "Minimal"', b'name = "' + 'α'.encode()*length + b'"'))
for codepoint in [0, 1, 9, 10, 13, 27, 31, 127, 128, 133, 159, 160, 0x200b, 0x2028, 0xfeff]:
    value = ('\\u%04x' % codepoint).encode()
    add('name-codepoint-' + str(codepoint), base.replace(b'name = "Minimal"', b'name = "' + value + b'"'))
marker = OUT / 'must-not-execute'
add('literal-shell-code', base.replace(b'prefix = " "', ('prefix = "$(touch ' + str(marker) + ') %F{red} `id`"').encode()))
for length in [65535, 65536, 65537]: add('file-size-' + str(length), base + b'#' + b'x'*(length-len(base)-2) + b'\n')
add('segment-missing-background', base + b'\n[segments.cwd]\n')
add('segment-disallowed-dirty', base + b'\n[segments.cwd]\nbackground = "blue"\ndirty-background = "red"\n')
add('segment-disabled-component', base + b'\n[segments.context]\nbackground = "blue"\n')
add('segment-valid-git-dirty', base + b'\n[segments.git]\nbackground = "blue"\ndirty-background = "red"\n')
add('optional-label', base.replace(b'[git]\n', b'[git]\nlabel-suffix = "ok"\n'))
add('repeated-component', base.replace(b'left = ["cwd", "git", "prompt-character"]', b'left = ["cwd", "cwd", "git", "prompt-character"]'))
randomizer = random.Random(20260908)
for index in range(1000):
    source = bytearray(base)
    for _ in range(index % 5 + 1): source[randomizer.randrange(len(source))] = randomizer.randrange(256)
    add('mutation-' + str(index), bytes(source))
results = []; failures = []
for index, (name, source) in enumerate(cases):
    path = OUT / 'input.toml'; path.write_bytes(source)
    observed = {}
    for variant, binary in [('rust', RUST), ('c', NATIVE)]:
        result = subprocess.run([binary, 'validate-theme', path], capture_output=True, env=environment, timeout=3)
        observed[variant] = dict(status=result.returncode, stdout=result.stdout.decode('utf-8', 'backslashreplace'), stderr=result.stderr.decode('utf-8', 'backslashreplace'))
    c = observed['c']; rust = observed['rust']
    passed = (rust['status'] == 0) == (c['status'] == 0) and c['status'] in (0, 1)
    passed = passed and not any(marker in c['stderr'] for marker in ['Sanitizer', 'runtime error:'])
    if rust['status'] == 0 and c['status'] == 0: passed = passed and rust['stdout'] == c['stdout']
    row = dict(index=index, case=name, input_sha256=hashlib.sha256(source).hexdigest(), passed=passed, observed=observed)
    results.append(row)
    if not passed:
        failures.append(row); (OUT / ('failure-' + str(index) + '.toml')).write_bytes(source)
    if index % 100 == 0: print(index, 'cases checked;', len(failures), 'differences', flush=True)
assert not marker.exists(), 'theme content executed'
(OUT / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
(OUT / 'metadata.json').write_text(json.dumps(dict(command='python3 native/test-theme-parity.py ' + ' '.join(sys.argv[1:]), binaries={name:dict(path=str(binary), sha256=hashlib.sha256(binary.read_bytes()).hexdigest()) for name,binary in [('rust',RUST),('c',NATIVE)]}, cases=len(cases), seed=20260908), indent=2) + '\n')
print(json.dumps(failures, indent=2))
assert not failures, [r['case'] for r in failures]
print('PASS:', len(cases), 'theme validation comparisons, including 1000 deterministic mutations')
