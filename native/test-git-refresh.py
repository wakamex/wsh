#!/usr/bin/env python3
"""A slow prompt status refreshes the index once in the background, never while index.lock exists."""
import json, os, select, subprocess, sys, time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
runtime, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
out.mkdir(parents=True)
checks = 0


def check(name, condition, detail=''):
    global checks
    assert condition, f'{name}: {detail}'
    checks += 1


def repository(name):
    repo = out / name
    repo.mkdir()
    for args in (['init', '-q', '-b', 'main'], ['config', 'user.name', 'refresh-test'], ['config', 'user.email', 'refresh@wsh.invalid']):
        subprocess.run(['git', '-C', repo, *args], check=True)
    for i in range(20):
        (repo / f'file{i}').write_text(f'{i}\n')
    subprocess.run(['git', '-C', repo, 'add', '.'], check=True)
    subprocess.run(['git', '-C', repo, 'commit', '-qm', 'seed'], check=True)
    # Same content, new stat data: the index entries are now stale.
    time.sleep(1.1)
    for i in range(20):
        os.utime(repo / f'file{i}')
    return repo


def stale(repo):
    """Entries whose saved mtime no longer matches the file."""
    listing = subprocess.run(['git', '-C', repo, 'ls-files', '--debug'], capture_output=True, text=True, check=True).stdout
    saved = {}
    name = None
    for line in listing.splitlines():
        if not line.startswith(' '):
            name = line
        elif line.strip().startswith('mtime:'):
            saved[name] = int(line.split(':')[1])
    return sum(1 for name, seconds in saved.items() if int((repo / name).stat().st_mtime) != seconds)


# A wrapper Git that makes status slow and logs refreshes, so the threshold is reached on any machine.
helper = out / 'bin'
helper.mkdir()
log = out / 'refreshes.log'
(helper / 'git').write_text(f'''#!/bin/sh
case "$1" in
  status) [ "$GIT_OPTIONAL_LOCKS" = 0 ] || exit 99; /usr/bin/sleep "${{WSH_TEST_STATUS_DELAY:-0}}" ;;
  update-index) printf '%s\\n' "$PWD" >> {log} ;;
esac
exec /usr/bin/git "$@"
''')
(helper / 'git').chmod(0o755)


class Runtime:
    def __init__(self, delay):
        env = dict(os.environ, PATH=f'{helper}:/usr/bin:/bin', WSH_TEST_STATUS_DELAY=delay)
        env.pop('GIT_INDEX_FILE', None)
        self.process = subprocess.Popen([runtime, 'serve', '--theme', root / 'themes/minimal.toml'], env=env,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.buffer = bytearray()
        self.id = 0
        assert self.read()['type'] == 'ready'

    def read(self):
        deadline = time.monotonic() + 5
        while b'\n' not in self.buffer:
            assert time.monotonic() < deadline, bytes(self.buffer)
            if select.select([self.process.stdout], [], [], .05)[0]:
                data = os.read(self.process.stdout.fileno(), 65536)
                assert data
                self.buffer.extend(data)
        line, _, rest = self.buffer.partition(b'\n')
        self.buffer[:] = rest
        return json.loads(line)

    def refresh(self, repo):
        self.id += 1
        message = dict(type='refresh', version=1, id=self.id, generation=self.id, cwd_hex=os.fsencode(repo).hex(), exit_status=0,
                       duration_ms=None, privileged=False, reset_transient=False)
        self.process.stdin.write(json.dumps(message).encode() + b'\n')
        self.process.stdin.flush()
        response = self.read()
        assert response['type'] == 'snapshot', response
        return response

    def close(self):
        self.process.kill()
        self.process.wait()


def refreshes(repo):
    return log.read_text().splitlines().count(str(repo)) if log.exists() else 0


def settle(repo, expected):
    deadline = time.monotonic() + (5 if expected < 99 else 1)
    while refreshes(repo) < expected and time.monotonic() < deadline:
        time.sleep(.05)
    # Let a running refresh finish and release its lock.
    while (repo / '.git/index.lock').exists() and time.monotonic() < deadline:
        time.sleep(.05)
    time.sleep(.2)


slow = Runtime('0.15')
try:
    repo = repository('slow')
    check('index starts stale', stale(repo) == 20, stale(repo))
    slow.refresh(repo)
    settle(repo, 1)
    check('slow status refreshes once', refreshes(repo) == 1, refreshes(repo))
    check('refresh saved stat data', stale(repo) == 0, stale(repo))
    counts = []
    for _ in range(6):
        slow.refresh(repo)
        settle(repo, 99)
        counts.append(refreshes(repo))
    # Git rewrites an index whose files changed within the same second as it, so a few refreshes
    # can follow one another; the first one that writes nothing ends the series.
    check('refreshes stop once the index is current', counts[-1] == counts[-4], counts)
    check('no lock left behind', not (repo / '.git/index.lock').exists())

    locked = repository('locked')
    (locked / '.git/index.lock').write_text('')
    slow.refresh(locked)
    settle(locked, 1)
    check('no refresh while index.lock exists', refreshes(locked) == 0, refreshes(locked))
    check('the lock holder keeps its lock', (locked / '.git/index.lock').exists())
    (locked / '.git/index.lock').unlink()
    slow.refresh(locked)
    settle(locked, 1)
    check('refresh once the lock is released', refreshes(locked) == 1 and stale(locked) == 0, (refreshes(locked), stale(locked)))

    rebasing = repository('rebasing')
    (rebasing / '.git/rebase-merge').mkdir()
    slow.refresh(rebasing)
    settle(rebasing, 1)
    check('no refresh during a rebase, merge or similar operation', refreshes(rebasing) == 0, refreshes(rebasing))
finally:
    slow.close()

fast = Runtime('0')
try:
    repo = repository('fast')
    for _ in range(3):
        fast.refresh(repo)
    settle(repo, 1)
    check('fast status does not refresh', refreshes(repo) == 0 and stale(repo) == 20, (refreshes(repo), stale(repo)))
finally:
    fast.close()
(out / 'results.json').write_text(json.dumps(dict(checks=checks), indent=2) + '\n')
print(f'PASS: {checks} background index refresh checks')
