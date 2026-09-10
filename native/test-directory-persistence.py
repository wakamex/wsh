#!/usr/bin/env python3
"""Exercise real Zsh flock interoperability, mixed writers and path round trips."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys

binary, module, fixture, out = [Path(p).resolve() for p in sys.argv[1:]]
out.mkdir(parents=True, exist_ok=True)
home = out / 'home'
home.mkdir(exist_ok=True)
project = home / 'project'
project.mkdir(exist_ok=True)
tab = home / 'tab\tpath'
tab.mkdir(exist_ok=True)
data = home / 'db'
script = out / 'run.zsh'
script.write_text('''module_path=($1 $module_path)
zmodload wshdirectory || exit 90
source "$2"
shift 2
zshz "$@"
''')
env = dict(os.environ, HOME=str(home), ZSHZ_DATA=str(data), WSH_QUERY_NOW='1800000000', LC_ALL='C.UTF-8', ZSHZ_LOCK_TIMEOUT='0.05')
def run(owner, *args):
    result = subprocess.run([binary, '-df', script, module, fixture / (owner + '.zsh'), *args], env=env, capture_output=True, timeout=10)
    return dict(status=result.returncode, stdout=result.stdout.hex(), stderr=result.stderr.hex(), database=data.read_bytes().hex())
rows = []
for owner in ('control', 'candidate'):
    data.write_text('')
    add = run(owner, '--add', str(tab))
    query = run(owner, '-e', 'tab')
    assert add['status'] == 0 and not add['stderr']
    assert query['status'] == (1 if owner == 'control' else 0) and not query['stderr']
    if owner == 'candidate':
        assert bytes.fromhex(query['stdout']) == (str(tab)+'\n').encode()
    rows.append(dict(test='tab-roundtrip', owner=owner, add=add, query=query))
    data.write_text(str(project) + '|2|1700000000\n')
    (home / 'db.lock').touch()
    holder = subprocess.Popen([binary, '-dfc', 'zmodload zsh/system; zsystem flock -t 1 -f lockfd "$1" || exit 1; print LOCKED; read -r release', 'lock', home / 'db.lock'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        assert holder.stdout.readline() == b'LOCKED\n'
        locked = run(owner, '--add', str(project))
        assert locked['status'] == 2 and not locked['stderr']
        rows.append(dict(test='real-zsh-flock-timeout', owner=owner, result=locked))
        assert bytes.fromhex(locked['database']) == (str(project) + '|2|1700000000\n').encode()
    finally:
        holder.communicate(b'release\n', timeout=5)
    unlocked = run(owner, '--add', str(project))
    rows.append(dict(test='lock-release-recovery', owner=owner, result=unlocked))
    assert unlocked['status'] == 0
# Authoritative pinned and native writers share the actual same lock and database.
env['ZSHZ_LOCK_TIMEOUT'] = '5'
data.write_text(str(project) + '|2|1700000000\n')
with ThreadPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(lambda n: run('control' if n % 2 else 'candidate', '--add', str(project)), range(20)))
rows.append(dict(test='twenty-mixed-writers', results=results, database=data.read_bytes().hex()))
assert all(r['status'] == 0 and not r['stderr'] for r in results)
assert data.read_text() == str(project) + '|22|1800000000\n'
(out / 'results.json').write_text(json.dumps(rows, indent=2) + '\n')
print(json.dumps([dict(test=r['test'], owner=r.get('owner'), status=r.get('result', r.get('query', {})).get('status')) for r in rows], indent=2))
