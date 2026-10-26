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
delay_file = out / 'status-delay'
# The status delay comes from a file when it exists, so a case can switch between slow and fast.
# A refresh records which index Git is given and, while the marker exists, is still hashing.
(helper / 'git').write_text(f'''#!/bin/sh
case "$1" in
  status) [ "$GIT_OPTIONAL_LOCKS" = 0 ] || exit 99
    delay=${{WSH_TEST_STATUS_DELAY:-0}}; [ -f {delay_file} ] && delay=$(cat {delay_file}); sleep "$delay" ;;
  update-index) printf '%s\\n' "$PWD" >> {log}; printf '%s\\n' "${{GIT_INDEX_FILE:-}}" >> {log}.index
    : > "$PWD/.git/hashing"; sleep "${{WSH_TEST_REFRESH_DELAY:-0}}"; /usr/bin/git "$@"; status=$?; rm -f "$PWD/.git/hashing"; exit $status ;;
esac
exec /usr/bin/git "$@"
''')
(helper / 'git').chmod(0o755)


class Runtime:
    def __init__(self, delay, refresh_delay='0'):
        env = dict(os.environ, PATH=f'{helper}:/usr/bin:/bin', WSH_TEST_STATUS_DELAY=delay, WSH_TEST_REFRESH_DELAY=refresh_delay)
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
        assert response['type'] in ('snapshot', 'error'), response
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
    # Let a running refresh finish hashing and release its lock.
    while ((repo / '.git/hashing').exists() or (repo / '.git/index.lock').exists()) and time.monotonic() < deadline:
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
    # A status that stays slow over a current index retries after 2, then 4 seconds, and so on, so
    # six prompts about a second apart start at most three more refreshes.
    check('retries over a current index back off', counts[-1] - counts[0] <= 3, counts)
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

def racy_unsmudged(repo):
    """Entries Git trusts without rehashing although their file is not older than the index, to the
    second as this Git compares. Git never writes such entries; each status would rehash them."""
    index_second = int((repo / '.git/index').stat().st_mtime)
    listing = subprocess.run(['git', '-C', repo, 'ls-files', '--debug'], capture_output=True, text=True, check=True).stdout
    racy, name, mtime = 0, None, None
    for line in listing.splitlines():
        if not line.startswith(' '):
            name = line
        elif line.strip().startswith('mtime:'):
            mtime = int(line.split(':')[1])
        elif line.strip().startswith('size:'):
            size = int(line.split(':')[1].split()[0])
            racy += mtime >= index_second and size > 0
    return racy


def touch(repo):
    time.sleep(1.1)
    for i in range(20):
        os.utime(repo / f'file{i}')


# A second batch of touched files is refreshed again once a refresh has helped.
slow = Runtime('0.15')
try:
    repo = repository('again')
    # Slow statuses until the refresh series ends, as in a shell that sat in the repository.
    for _ in range(5):
        slow.refresh(repo)
        settle(repo, 99)
    delay_file.write_text('0')
    slow.refresh(repo)
    touch(repo)
    delay_file.write_text('0.15')
    before = refreshes(repo)
    slow.refresh(repo)
    settle(repo, before + 1)
    check('touched again after a fast status refreshes again', refreshes(repo) > before and stale(repo) == 0, (refreshes(repo), stale(repo)))
finally:
    slow.close()
    delay_file.unlink(missing_ok=True)

# Git hashes a private copy; index.lock is never held while it does, so a user's git add works.
slow = Runtime('0.15', refresh_delay='0.5')
try:
    repo = repository('private')
    slow.refresh(repo)
    deadline = time.monotonic() + 5
    while not (repo / '.git/hashing').exists() and time.monotonic() < deadline:
        time.sleep(.005)
    hashing = locked_seen = 0
    adds = []
    while (repo / '.git/hashing').exists() and time.monotonic() < deadline:
        hashing += 1
        locked_seen += (repo / '.git/index.lock').exists()
        adds.append(subprocess.run(['/usr/bin/git', '-C', repo, 'add', 'file0'], capture_output=True).returncode)
    settle(repo, 1)
    given = Path(str(log) + '.index').read_text().splitlines()[-1]
    check('refresh hashes a private copy of the index', given.startswith(str(repo / '.git/index.wsh-')), given)
    check('index.lock is not held while Git hashes', hashing > 0 and locked_seen == 0, (hashing, locked_seen))
    check("the user's git add succeeds during a refresh", adds and not any(adds), adds)
    # The user's adds replaced the index meanwhile, so the copy was discarded instead of
    # overwriting their change; the next slow status retries.
    check('a copy is discarded when the index changed meanwhile', stale(repo) > 0, stale(repo))
    slow.refresh(repo)
    settle(repo, 2)
    check('the next slow status installs a fresh refresh', stale(repo) == 0, stale(repo))
    check('the private copy is removed', not list((repo / '.git').glob('index.wsh-*')), list((repo / '.git').glob('index.wsh-*')))
finally:
    slow.close()

# A refresh in the same second as the touch leaves no entry that is racy yet trusted.
slow = Runtime('0.15')
try:
    repo = repository('same-second')
    while time.time() % 1 > .2:
        time.sleep(.01)
    for i in range(20):
        os.utime(repo / f'file{i}')
    slow.refresh(repo)
    settle(repo, 1)
    check('a same-second refresh leaves no racy trusted entry', racy_unsmudged(repo) == 0, racy_unsmudged(repo))
finally:
    slow.close()

# A status past the collector's 2-second limit still starts the refresh.
slow = Runtime('2.5')
try:
    repo = repository('timeout')
    response = slow.refresh(repo)
    check('the status times out', response['type'] == 'error' and 'timed out' in response.get('error', ''), response)
    settle(repo, 1)
    check('a timed-out status refreshes', refreshes(repo) == 1 and stale(repo) == 0, (refreshes(repo), stale(repo)))
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
