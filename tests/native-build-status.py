#!/usr/bin/env python3
"""Compile the real native dispatcher with both production-generated headers."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT/'build/zsh-sources/zsh-cad0d67c-native.json'
version = json.loads(LOCK.read_text())['native']['version']
with tempfile.TemporaryDirectory(prefix='wsh-build-status-') as tmp:
    home = Path(tmp)
    (home/'.zshenv').write_text('print STARTUP_LEAK; exit 91\n')
    (home/'manifest.json').write_text('{broken mutable metadata')
    env = dict(os.environ, HOME=tmp, ZDOTDIR=tmp, WSH_SOURCE_REVISION='a'*40)
    identities = {}
    for status, label in (('development','unsigned development artifact'), ('release','release build')):
        work = home/status
        (work/'Src').mkdir(parents=True)
        build_env = dict(env, WSH_BUNDLE_STATUS=status)
        prepared = subprocess.run(['python3',ROOT/'native/prepare-build.py',LOCK,work], env=build_env, check=True, capture_output=True, text=True)
        identities[status] = prepared.stdout.strip()
        # Compile the exact dispatcher used by the shell, without rebuilding
        # unrelated Zsh components for this build-mode matrix.
        shutil.copyfile(ROOT/'native/tools.c', work/'Src/tools.c')
        harness = work/'Src/driver.c'
        harness.write_text('#include <stdio.h>\n#include <string.h>\n'
                           '#define WSH_CLI_STANDALONE 1\n#define ZSH_VERSION "test"\n'
                           '#include "tools.c"\n'
                           'int main(int argc, char **argv) { int code=wsh_cli(argc,argv); return code<0 ? 99 : code; }\n')
        binary = work/'wsh'
        subprocess.run([os.environ.get('CC','cc'),'-std=c99','-Wall','-Wextra','-Werror',harness,'-o',binary],check=True)
        def run(arguments, runtime_status):
            return subprocess.run([binary,*arguments],cwd=home,env=dict(env,WSH_BUNDLE_STATUS=runtime_status),capture_output=True,text=True,timeout=5)
        for runtime_status in ('development','release','invalid'):
            result = run(['--wsh-version'],runtime_status)
            assert result.returncode == 0 and not result.stderr
            assert result.stdout.splitlines()[0] == f'wsh {version} ({label})'
            assert 'identity: compiled build; installed resources not verified' in result.stdout
            assert 'STARTUP_LEAK' not in result.stdout
        for option in ('--wsh-version','--wsh-help'):
            assert run([option,'extra'],status).returncode == 2
        assert run(['--wsh-help'],status).returncode == 0
        assert run(['--version'],status).returncode == 99
        assert run(['--','--wsh-version'],status).returncode == 99
        assert run(['version'],status).returncode == 99
    assert identities['development'] != identities['release']
    default_env = dict(env)
    default_env.pop('WSH_BUNDLE_STATUS',None)
    default = subprocess.check_output(['python3',ROOT/'native/prepare-build.py',LOCK],env=default_env,text=True).strip()
    assert default == identities['development']
    for invalid in ('','official','Release','release\n#define SPOOF 1'):
        result = subprocess.run(['python3',ROOT/'native/prepare-build.py',LOCK],env=dict(env,WSH_BUNDLE_STATUS=invalid),capture_output=True,text=True)
        assert result.returncode != 0 and not result.stdout and 'invalid WSH_BUNDLE_STATUS' in result.stderr
print('PASS: compiled development/release labels, cache separation, default/invalid modes, runtime isolation and CLI boundaries')

# The canonical installation suite supplies its freshly built installation.
if len(sys.argv) == 2:
    bundle = Path(sys.argv[1]).resolve()
    manifest = json.loads((bundle/'manifest.json').read_text())
    expected = 'release build' if manifest['status'] == 'release' else 'unsigned development artifact'
    with tempfile.TemporaryDirectory(prefix='wsh-installed-version-') as tmp:
        home = Path(tmp)
        (home/'.zshenv').write_text('print STARTUP_LEAK; exit 91\n')
        (home/'manifest.json').write_text('{broken')
        env = dict(PATH='/usr/bin:/bin', HOME=tmp, ZDOTDIR=tmp, WSH_BUNDLE_STATUS='invalid', WSH_STATE_ROOT=tmp)
        def run(binary, args):
            return subprocess.run([binary,*args], cwd=home, env=env, capture_output=True, text=True, timeout=10)
        executable = bundle/'bin/wsh'
        result = run(executable,['--wsh-version'])
        assert result.returncode == 0 and not result.stderr
        assert result.stdout.splitlines()[0] == f"wsh {manifest['version']} ({expected})"
        assert 'STARTUP_LEAK' not in result.stdout
        moved = home/'relocated-wsh'
        shutil.copyfile(executable,moved)
        moved.chmod(0o755)
        assert run(moved,['--wsh-version']).stdout == result.stdout
        assert run(executable,['--wsh-version','extra']).returncode == 2
        assert run(executable,['--wsh-help']).returncode == 0
        assert run(executable,['--version']).stdout.startswith('zsh ')
        (home/'.zshenv').write_text('')
        (home/'version').write_text('print -r -- "$1"; exit 23\n')
        result = run(executable,['-f','version','literal argument'])
        assert result.returncode == 23 and result.stdout == 'literal argument\n'
        result = run(executable,['-dfc','print -r -- NATIVE_SHELL_OK'])
        assert result.returncode == 0 and result.stdout == 'NATIVE_SHELL_OK\n'
    print('PASS: installed label, missing resources, corrupt metadata, startup isolation and native shell arguments')
