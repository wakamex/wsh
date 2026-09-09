#!/usr/bin/env python3
"""Exercise old-inode module ownership and the real external module loader."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

bundle, external, replacement, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
installation = output / 'installation'
shutil.copytree(bundle, installation)
script = output / 'probe.zsh'
script.write_text('''print -r -- WSH_WAITING
read -r reply
zmodload zsh/stat || exit 3
zmodload zsh/system || exit 4
zmodload zsh/datetime || exit 5
zmodload -u zsh/stat || exit 6
zmodload zsh/stat || exit 7
module_path=($1 $module_path)
zmodload wshsuggest || exit 8
(( $+builtins[wsh-history-suggest] )) || exit 9
zmodload -u wshsuggest || exit 10
zmodload wshsuggest || exit 11
print -r -- WSH_LINKED_AND_EXTERNAL_OK
''')
env = dict(PATH='/usr/bin:/bin', HOME=str(output), LC_ALL='C.UTF-8')
env.update({k: os.environ[k] for k in ('ASAN_OPTIONS', 'UBSAN_OPTIONS') if k in os.environ})
child = subprocess.Popen([installation / 'bin/wsh', '-df', script, external], env=env,
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
try:
    assert child.stdout.readline() == b'WSH_WAITING\n'
    before = os.readlink(f'/proc/{child.pid}/exe')
    target = installation / 'bin/wsh'
    staged = installation / 'bin/replacement'
    shutil.copyfile(replacement, staged)
    staged.chmod(0o755)
    staged.replace(target)
    after = os.readlink(f'/proc/{child.pid}/exe')
    assert after.endswith(' (deleted)')
    shutil.rmtree(installation / 'lib')
    stdout, stderr = child.communicate(b'continue\n', timeout=10)
    assert child.returncode == 0 and stdout == b'WSH_LINKED_AND_EXTERNAL_OK\n' and not stderr, (child.returncode, stdout, stderr)
finally:
    if child.poll() is None:
        child.kill()
        child.wait()
(output / 'results.json').write_text(json.dumps(dict(before=before, after=after, status=child.returncode,
    stdout=stdout.decode(), stderr=stderr.decode(), passed=True), indent=2) + '\n')
print('PASS: old executable inode retains bundled modules; external modules load and reload')
