#!/usr/bin/env python3
"""Exercise real file bind mounts in a private user/mount namespace or container."""
from concurrent.futures import ThreadPoolExecutor
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys

binary, module, fixture, out = [Path(p).resolve() for p in sys.argv[1:5]]
baseline = '--baseline' in sys.argv[5:]
out.mkdir(parents=True, exist_ok=True)
home = out/'home'
home.mkdir(exist_ok=True)
project = home/'project'
project.mkdir(exist_ok=True)
source = home/'source'
data = home/'db'
data.touch()
script = out/'run.zsh'
script.write_text('''module_path=($1 $module_path)
zmodload wshdirectory || exit 90
source "$2"
zshz --add "$HOME/project"
''')
env = dict(os.environ, HOME=str(home), ZSHZ_DATA=str(data), WSH_QUERY_NOW='1800000000', LC_ALL='C.UTF-8')
libc = ctypes.CDLL(None, use_errno=True)
rows = []
for owner in (('candidate',) if '--native-only' in sys.argv[5:] else ('control', 'candidate')):
    for readonly in (False, True):
        source.write_text(str(project)+'|2|1700000000\n')
        source.chmod(0o644)
        before = source.read_bytes()
        subprocess.run(['mount', '--bind', source, data], check=True)
        try:
            if readonly:
                assert libc.mount(None, os.fsencode(data), None, 4096 | 32 | 1, None) == 0, ctypes.get_errno()
            inode = data.stat().st_ino
            result = subprocess.run([binary, '-df', script, module, fixture/(owner+'.zsh')], env=env, capture_output=True, timeout=10)
            row = dict(owner=owner, readonly=readonly, status=result.returncode, stdout=result.stdout.hex(), stderr=result.stderr.hex(), before=before.hex(), database=data.read_bytes().hex(), inode_preserved=data.stat().st_ino == inode == source.stat().st_ino, mode=data.stat().st_mode & 0o777)
            rows.append(row)
            (out/'results.json').write_text(json.dumps(rows, indent=2)+'\n')
            if not baseline or owner == 'control':
                assert row['inode_preserved'], row
                if readonly:
                    assert result.returncode != 0 and data.read_bytes() == before, row
                else:
                    assert result.returncode == 0 and data.read_text() == str(project)+'|3|1800000000\n' and row['mode'] == 0o600, row
                    if owner == 'candidate' and '--native-only' not in sys.argv[5:]:
                        def write(n):
                            return subprocess.run([binary, '-df', script, module, fixture/(('control' if n % 2 else 'candidate')+'.zsh')], env=env, capture_output=True, timeout=10)
                        with ThreadPoolExecutor(max_workers=4) as pool:
                            writers = list(pool.map(write, range(20)))
                        assert all(w.returncode == 0 and not w.stderr for w in writers)
                        assert source.read_text() == str(project)+'|23|1800000000\n'
                        row['mixed_writers'] = 20
                        row['mixed_database'] = source.read_bytes().hex()
                        (out/'results.json').write_text(json.dumps(rows, indent=2)+'\n')
        finally:
            assert libc.umount(os.fsencode(data)) == 0, ctypes.get_errno()
print(json.dumps(rows, indent=2))
