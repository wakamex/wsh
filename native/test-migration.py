#!/usr/bin/env python3
"""Test manual PATH migration without changing live dotfiles or account shells."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

bundle = Path(sys.argv[1]).resolve()
manager = Path(sys.argv[2]).resolve()
out = Path(sys.argv[3]).resolve()
out.mkdir(parents=True, exist_ok=True)
results = []
with tempfile.TemporaryDirectory(prefix='wsh-migration-') as temporary:
    root = Path(temporary)
    home = root / 'home'
    old = home / '.local/bin'
    old.mkdir(parents=True)
    shutil.copy2(manager, old / 'wsh')
    system = root / 'system'
    shutil.copytree(bundle, system)
    state = home / '.local/share/wsh'
    state.mkdir(parents=True)
    (state / 'bundle-state.json').write_text('{broken legacy activation state\n')
    (home / '.zsh_history').write_text(': 1:0;echo preserved\n')
    (home / 'custom.toml').write_text((bundle / 'share/wsh/themes/minimal.toml').read_text())
    (home / '.zshenv').write_text('unsetopt globalrcs\n')
    (home / '.zshrc').write_text('WSH_THEME=minimal\nPROMPT="shared> "\n')
    protected = [p for p in home.rglob('*') if p.is_file()]
    before = {str(p.relative_to(home)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    env = dict(HOME=str(home), ZDOTDIR=str(home), TERM='xterm-256color', LC_ALL='C.UTF-8', PATH=str(old)+':'+str(system/'bin')+':/usr/bin:/bin')
    def run(binary, argv, expected=0):
        result = subprocess.run([str(binary), *argv], env=env, cwd=root, input=b'', capture_output=True, timeout=15)
        assert result.returncode == expected, (argv, result)
        return result.stdout
    assert run(system/'bin/wsh', ['-dfc', 'whence -p wsh']).strip() == os.fsencode(old/'wsh')
    build_status = json.loads((bundle/'manifest.json').read_text())['status']
    label = b'release build' if build_status == 'release' else b'unsigned development artifact'
    assert label in run(system/'bin/wsh', ['--wsh-version'])
    assert run(system/'bin/wsh', ['-dlc', 'print -r -- NATIVE:$ZSH_VERSION']).startswith(b'NATIVE:')
    results.append({'case': 'absolute native path works despite earlier legacy launcher and corrupt private state', 'passed': True})
    # The user can retire only the executable after testing the package and account shell.
    (old/'wsh').rename(old/'wsh-legacy')
    assert run(system/'bin/wsh', ['-dfc', 'rehash; whence -p wsh']).strip() == os.fsencode(system/'bin/wsh')
    assert run(old/'wsh-legacy', ['--version']).startswith(b'wsh ')
    results.append({'case': 'retire legacy command name, refresh lookup, preserve explicit legacy manager', 'passed': True})
    for name in ('doctor', 'profile', 'version', 'update', 'run'):
        (root/name).write_text('print -r -- SCRIPT:$0:$1; exit 17\n')
        assert run(system/'bin/wsh', [name, 'argument'], 17) == ('SCRIPT:'+name+':argument\n').encode()
    results.append({'case': 'legacy command words remain ordinary native Zsh script names', 'passed': True})
    (old/'wsh-legacy').rename(old/'wsh')
    after = {str(p.relative_to(home)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    assert before == after
    results.append({'case': 'configuration, history, local theme, activation state and legacy executable remain unchanged', 'passed': True, 'files': before})
(out/'results.json').write_text(json.dumps(results, indent=2)+'\n')
print('PASS: private PATH migration, explicit legacy access, script semantics and user-data preservation')
