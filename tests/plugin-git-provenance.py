#!/usr/bin/env python3
"""Exercise local provenance against real Git repositories and raw object reads."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
bundle, output = map(lambda p: Path(p).resolve(), sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null', GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid', GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid')
rows = []


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], env=env, stderr=subprocess.PIPE).decode().strip()


def check(name, repo, component, paths, expected, *, catalog=False):
    script = '''typeset -g WSH_BUNDLE_ROOT=$1
source $WSH_BUNDLE_ROOT/share/wsh/defaults/plugin-recognition.zsh
shift
'''
    script += ('_wsh_plugin_recognized' if catalog else '_wsh_plugin_git_recognized') + ' "$@"\n'
    result = subprocess.run(['/usr/bin/zsh', '-dfc', script, 'test', str(bundle), component, *map(str, paths)], env=env, capture_output=True, timeout=15)
    assert (result.returncode == 0) == expected, (name, result.returncode, result.stderr.decode())
    rows.append(dict(case=name, accepted=expected, passed=True))


with tempfile.TemporaryDirectory(prefix='wsh-git-provenance-') as tmp:
    root = Path(tmp)
    repo = root / 'repository with spaces\n'
    repo.mkdir()
    git(repo, 'init', '-b', 'master')
    filename = 'zsh-autosuggestions.zsh'
    source = repo / filename
    data = (ROOT / 'third_party/zsh-autosuggestions/known-0.7.0.zsh').read_bytes() + b'\n# upstream fixture outside catalog\n'
    source.write_bytes(data)
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'upstream fixture')
    base = git(repo, 'rev-parse', 'HEAD')
    official = 'https://github.com/zsh-users/zsh-autosuggestions.git'
    git(repo, 'remote', 'add', 'origin', official)
    git(repo, 'update-ref', 'refs/remotes/origin/master', base)
    def test(name, expected=True, **kw):
        check(name, repo, 'autosuggestions', [source], expected, **kw)
    test('clean upstream bytes with spaces and newline root')
    test('catalog miss reaches Git', catalog=True)
    (repo/'unrelated').write_text('user theme\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'unrelated local change')
    test('unrelated local commit')
    source.write_bytes(data + b'# user edit\n')
    test('unstaged relevant edit', False)
    git(repo, 'update-index', '--assume-unchanged', filename)
    test('assume-unchanged cannot hide edit', False)
    git(repo, 'update-index', '--no-assume-unchanged', filename)
    git(repo, 'add', filename)
    test('staged relevant edit', False)
    git(repo, 'commit', '-m', 'local relevant edit')
    test('committed relevant edit', False)
    git(repo, 'reset', '--hard', base)
    git(repo, 'config', 'remote.origin.url', 'https://github.com/example/fork')
    test('fork-only remote', False)
    for url in (official, 'git@github.com:zsh-users/zsh-autosuggestions.git', 'ssh://git@github.com/zsh-users/zsh-autosuggestions.git'):
        git(repo, 'config', 'remote.origin.url', url)
        test('official URL ' + url)
    git(repo, 'update-ref', '-d', 'refs/remotes/origin/master')
    test('missing tracking reference', False)
    git(repo, 'update-ref', 'refs/remotes/origin/master', base)
    git(repo, 'config', 'remote.origin.promisor', 'true')
    test('partial clone refused', False)
    git(repo, 'config', '--unset', 'remote.origin.promisor')
    git(repo, 'config', 'extensions.partialclone', 'origin')
    test('partial clone extension refused', False)
    git(repo, 'config', '--unset', 'extensions.partialclone')
    git(repo, 'config', 'remote.oversized.url', 'x' * 65537)
    test('oversized remote configuration', False)
    git(repo, 'config', '--unset', 'remote.oversized.url')
    marker = root/'filter-ran'
    git(repo, 'config', 'filter.fixture.clean', 'touch ' + str(marker))
    git(repo, 'config', 'diff.fixture.textconv', 'touch ' + str(marker))
    (repo/'.gitattributes').write_text('*.zsh filter=fixture diff=fixture\n')
    test('raw reads bypass clean filters and textconv')
    assert not marker.exists()
    (repo/'.gitattributes').unlink()
    link = root/'symlink'
    link.symlink_to(repo, target_is_directory=True)
    check('symlinked checkout', repo, 'autosuggestions', [link/filename], True)
    worktree = root/'linked worktree'
    git(repo, 'worktree', 'add', '--detach', str(worktree), base)
    check('linked worktree', repo, 'autosuggestions', [worktree/filename], True)
    source.unlink()
    test('missing file', False)
    source.write_bytes(b'')
    test('empty file', False)
    source.write_bytes(b'x' * 131073)
    test('oversized file', False)
    source.write_bytes(data)
    git(repo, 'checkout', '--orphan', 'independent')
    source.write_bytes(data + b'# separate history\n')
    git(repo, 'add', filename)
    git(repo, 'commit', '-m', 'unrelated history')
    test('no common ancestor', False)
    git(repo, 'checkout', '--detach', base)
    # The index and replacement-object mechanism must not substitute local bytes.
    source.write_bytes(data + b'# replacement\n')
    git(repo, 'add', filename)
    git(repo, 'commit', '-m', 'replacement')
    replacement = git(repo, 'rev-parse', 'HEAD')
    git(repo, 'replace', base, replacement)
    test('replacement object cannot authorize local edit', False)
    git(repo, 'replace', '-d', base)
    for label, content, accepted in (
        ('empty upstream blob', b'', False),
        ('oversized upstream blob', b'x' * 131073, False),
        ('binary and trailing delimiters', b'raw\x00bytes\n\x1e\n', True),
    ):
        source.write_bytes(content)
        git(repo, 'add', filename)
        git(repo, 'commit', '-m', label)
        git(repo, 'update-ref', 'refs/remotes/origin/master', 'HEAD')
        test(label, accepted)
    downloaded = root/'download.zsh'
    downloaded.write_bytes((ROOT/'third_party/zsh-autosuggestions/known-0.7.0.zsh').read_bytes())
    check('downloaded catalog fallback', root, 'autosuggestions', [downloaded], True, catalog=True)
    downloaded.write_bytes(data)
    check('uncataloged download remains external', root, 'autosuggestions', [downloaded], False, catalog=True)
    # Every configured component/path mapping uses the same real Git contract.
    catalog = json.loads((ROOT/'third_party/plugin-catalog/catalog.json').read_text())['entries']
    for i, upstream in enumerate(json.loads((ROOT/'third_party/plugin-catalog/upstreams.json').read_text())['upstreams']):
        fixture = root / ('component-' + str(i))
        fixture.mkdir()
        git(fixture, 'init', '-b', 'master')
        entry = next(e for e in catalog if e['component'] == upstream['component'] and e['repository'] == upstream['repository'] and [f['upstream_path'] for f in e['files']] == upstream['paths'])
        paths = []
        for record in entry['files']:
            target = fixture / record['upstream_path']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/record['source']).read_bytes() + b'\n# upstream fixture\n')
            paths.append(target)
        git(fixture, 'add', '.')
        git(fixture, 'commit', '-m', 'upstream fixture')
        git(fixture, 'remote', 'add', 'origin', upstream['repository'])
        git(fixture, 'update-ref', 'refs/remotes/origin/master', 'HEAD')
        check('mapping ' + str(i), fixture, upstream['component'], paths, True)
        for j, target in enumerate(paths):
            original = target.read_bytes()
            target.write_bytes(original + b'# edited\n')
            check('mapping ' + str(i) + ' modified file ' + str(j), fixture, upstream['component'], paths, False)
            target.write_bytes(original)
    git(repo, 'config', 'remote.origin.url', 'https://github.com/example/fork')
    for i in range(8):
        git(repo, 'remote', 'add', 'missing-' + str(i), official)
    git(repo, 'remote', 'add', 'last', official)
    git(repo, 'update-ref', 'refs/remotes/last/master', 'HEAD')
    test('at most eight matching remotes', False)
    # A timed-out actual Git alias would not exercise the builtin; supplement
    # real Git coverage with a sleeping executable to test the timeout boundary.
    commands = root/'commands'
    commands.mkdir()
    sleeper = commands/'git'
    sleeper.write_text('#!/bin/sh\nexec /usr/bin/sleep 10\n')
    sleeper.chmod(0o755)
    old_path = env['PATH']
    env['PATH'] = str(commands) + ':' + old_path
    import time
    started = time.monotonic()
    test('Git timeout refuses takeover', False)
    elapsed = time.monotonic() - started
    assert elapsed < 2, elapsed
    env['PATH'] = old_path
(output/'results.json').write_text(json.dumps(rows, indent=2)+'\n')
print('PASS:', len(rows), 'Git provenance boundary cases')
