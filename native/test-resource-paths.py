#!/usr/bin/env python3
"""Prove relocation removes compiled fallbacks while preserving explicit FPATH."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

bundle, compiled, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
relocated = output / 'relocated installation'
shutil.copytree(bundle, relocated)
env = dict(PATH='/usr/bin:/bin', HOME=str(output), LC_ALL='C.UTF-8', TERM='xterm-256color')
env.update({key: os.environ[key] for key in ('ASAN_OPTIONS', 'UBSAN_OPTIONS') if key in os.environ})
query = 'print -rl -- $fpath; print -- WSH_MODULES; print -rl -- $module_path'
def run(code, extra=None):
    result = subprocess.run([relocated / 'bin/wsh', '-dfc', code], env=dict(env, **(extra or {})),
                            capture_output=True, timeout=10)
    assert result.returncode == 0 and not result.stderr, result
    return result.stdout.decode().splitlines()
defaults = run(query)
assert not any(str(compiled) in p for p in defaults), defaults
assert defaults[0] == str(relocated / 'share/zsh/5.9.999.3-test/functions')
assert defaults[-1] == str(relocated / 'lib/zsh/5.9.999.3-test')
assert '/usr/local/share/zsh/site-functions' in defaults
custom = output / 'custom functions'
custom.mkdir()
(custom / 'wsh_custom_probe').write_text('print -r -- WSH_CUSTOM_OK\n')
explicit = str(custom) + ':' + str(compiled / 'share/zsh/5.9.999.3-test/functions')
paths = run(query, dict(FPATH=explicit))
assert paths[1:3] == explicit.split(':'), paths
assert run('autoload -Uz wsh_custom_probe; wsh_custom_probe', dict(FPATH=explicit)) == ['WSH_CUSTOM_OK']
assert run('zmodload zsh/datetime; autoload -Uz is-at-least; is-at-least 5.9; print WSH_RESOURCES_OK') == ['WSH_RESOURCES_OK']
# A missing relocated function must not silently resolve from the still-present build tree.
function = 'is-at-least'
(relocated / 'share/zsh/5.9.999.3-test/functions' / function).unlink()
failed = subprocess.run([relocated / 'bin/wsh', '-dfc', 'autoload -Uz is-at-least; is-at-least 5.9'],
                        env=env, capture_output=True, timeout=10)
assert failed.returncode != 0 and b'function definition file not found' in failed.stderr, failed
(output / 'results.json').write_text(json.dumps(dict(defaults=defaults, explicit_paths=paths,
    missing_function_status=failed.returncode, missing_function_stderr=failed.stderr.decode(), passed=True), indent=2) + '\n')
print('PASS: relocated resource ownership, explicit FPATH, native module loading and no build-tree fallback')
