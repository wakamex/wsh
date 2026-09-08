#!/usr/bin/env python3
"""Compare complete snapshots against the retained Rust collector on real Git states."""
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RUNTIMES = dict(rust=Path(sys.argv[1]).resolve(), native=Path(sys.argv[2]).resolve())
OUT = Path(sys.argv[3]).resolve(); OUT.mkdir(parents=True)
home = OUT / 'home'; home.mkdir()
env = dict(HOME=str(home), PATH='/usr/bin:/bin', LC_ALL='C.UTF-8', TZ='UTC', GIT_CONFIG_NOSYSTEM='1')
env.update({key: os.environ[key] for key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS', 'LSAN_OPTIONS') if key in os.environ})
repo = OUT / 'repo'; repo.mkdir()
results = []

def git(*args, cwd=repo, expected=0):
    r = subprocess.run(['git', '-C', cwd, *args], env=env, capture_output=True, timeout=8)
    assert r.returncode == expected, (args, r.stdout, r.stderr)
    return r.stdout.strip()

def snapshot(binary, cwd, environment, parent=None):
    p = subprocess.Popen([binary, 'serve', '--theme', ROOT / 'themes/minimal.toml'], env=environment, cwd=parent, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    buffer = bytearray()
    def read():
        deadline = time.monotonic() + 4
        while b'\n' not in buffer:
            assert time.monotonic() < deadline, bytes(buffer)
            if select.select([p.stdout], [], [], .05)[0]:
                block = os.read(p.stdout.fileno(), 65536); assert block, p.poll()
                buffer.extend(block)
        line, _, rest = buffer.partition(b'\n'); buffer[:] = rest
        return json.loads(line)
    def send(value): p.stdin.write(json.dumps(value).encode() + b'\n'); p.stdin.flush()
    try:
        assert read()['type'] == 'ready'
        send(dict(type='refresh', version=1, id=2**64-1, generation=2**64-1, cwd_hex=os.fsencode(cwd).hex(), exit_status=0, duration_ms=None, privileged=False, reset_transient=False))
        response = read()
        send(dict(type='shutdown', version=1, id=2)); assert read()['type'] == 'stopping'
        assert p.wait(timeout=3) == 0
        diagnostics = p.stderr.read()
        assert not diagnostics, diagnostics
        if response['type'] == 'snapshot':
            assert response['generation'] == 2**64-1 and response['id'] == 2**64-1
            return response['snapshot']
        return {'error_type': response['type'], 'error': response.get('error')}
    finally:
        if p.poll() is None: p.kill(); p.wait()

def compare(name, cwd=repo, environment=env, parent=None, error=False):
    outputs = {variant: snapshot(binary, cwd, environment, parent) for variant, binary in RUNTIMES.items()}
    # Exact snapshot parity; error text is diagnostic rather than a protocol enum.
    passed = (all(o.get('error_type') == 'error' for o in outputs.values()) if error else
              outputs['rust'] == outputs['native'] and all('error_type' not in o for o in outputs.values()))
    results.append(dict(case=name, passed=passed, snapshots=outputs))
    (OUT / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(name, 'PASS' if passed else 'FAIL', flush=True)

git('init', '-q', '-b', 'main'); git('config', 'user.name', 'matrix'); git('config', 'user.email', 'matrix@wsh.invalid')
compare('unborn')
(repo / 'file').write_text('base\n'); git('add', 'file'); git('commit', '-qm', 'base')
initial = git('rev-parse', 'HEAD').decode()
compare('clean')
(repo / 'file').write_text('staged\n'); git('add', 'file'); compare('staged')
(repo / 'file').write_text('modified\n'); compare('staged-and-modified')
for name in [b'space name', b'line\nname', b'\xff%F{red}']:
    with open(os.fsencode(repo) + b'/' + name, 'wb') as f: f.write(b'untracked\n')
compare('untracked-hostile-filenames')
git('reset', '--hard', '-q', 'HEAD'); git('clean', '-fdq')
git('checkout', '-qb', 'topic/$()%F{red}'); compare('literal-prompt-metacharacters-in-branch')
git('checkout', '-q', '--detach', 'HEAD'); compare('detached')
git('tag', '-am', 'annotation', 'v1'); compare('annotated-tag')
git('pack-refs', '--all', '--prune'); compare('packed-annotated-tag')
git('tag', '-d', 'v1'); git('tag', 'α'); git('tag', b'\xc0'); compare('non-utf8-loose-tag-sorting')
git('pack-refs', '--all', '--prune'); compare('non-utf8-packed-tags')
git('checkout', '-q', 'main'); compare('non-utf8-packed-tags-with-symbolic-head')
git('tag', '-d', 'α', b'\xc0'); git('pack-refs', '--all', '--prune'); git('checkout', '-q', 'main')
linked = OUT / 'linked space'; git('worktree', 'add', '-qb', 'linked', linked)
compare('linked-worktree', linked)
nested = repo / 'nested'; nested.mkdir(); git('init', '-q', '-b', 'nested', cwd=nested); compare('nested-repository', nested)
# A relative PATH entry resolves from the requested absolute working directory.
helper = repo / 'bin'; helper.mkdir(); (helper / 'git').write_text('#!/bin/sh\nexec /usr/bin/git "$@"\n'); (helper / 'git').chmod(0o755)
compare('relative-path-entry', repo, dict(env, PATH='bin'), OUT)
compare('relative-cwd-rejected', 'repo', dict(env, PATH='bin'), OUT, error=True)
import shutil
shutil.rmtree(helper); shutil.rmtree(nested)
# Actual conflicted operations, rather than only fabricated marker files.
git('checkout', '-qb', 'other'); (repo / 'file').write_text('other\n'); git('commit', '-qam', 'other')
other = git('rev-parse', 'HEAD').decode()
git('checkout', '-q', 'main'); (repo / 'file').write_text('main\n'); git('commit', '-qam', 'main')
main = git('rev-parse', 'HEAD').decode()
git('merge', 'other', expected=1); compare('merge-conflict'); git('merge', '--abort')
git('rebase', 'other', expected=1); compare('rebase-conflict'); git('rebase', '--abort')
git('cherry-pick', other, expected=1); compare('cherry-pick-conflict'); git('cherry-pick', '--abort')
(repo / 'file').write_text('third\n'); git('commit', '-qam', 'third')
git('revert', '--no-edit', main, expected=1); compare('revert-conflict'); git('revert', '--abort')
git('bisect', 'start', 'HEAD', initial); compare('bisect'); git('bisect', 'reset')
# Preserve raw path bytes through the complete wire snapshot.
raw = os.fsencode(OUT) + b'/raw-\xff-space name'; os.mkdir(raw); git('init', '-q', '-b', 'raw', cwd=raw); compare('non-utf8-repository-path', raw)
compare('outside-repository', home)
(OUT / 'metadata.json').write_text(json.dumps(dict(runtimes={v:dict(path=str(b), sha256=hashlib.sha256(b.read_bytes()).hexdigest()) for v,b in RUNTIMES.items()}, command='python3 native/test-git-matrix.py ' + ' '.join(sys.argv[1:]), environment=env), indent=2) + '\n')
assert all(r['passed'] for r in results), [r['case'] for r in results if not r['passed']]
print('PASS: real Git matrix and unsigned-64-bit generation/id parity')
