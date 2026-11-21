#!/usr/bin/env python3
"""Check an installed Wsh RPM in a disposable Fedora guest, as root.

Usage: test-hosted-rpm.py VERSION-RELEASE SOURCE_REVISION, for example 0.4.9-1.fc45 and the tagged commit.
"""
from pathlib import Path
import subprocess
import sys

expected_release, expected_source = sys.argv[1:3]

def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)

assert Path('/usr/bin/wsh').is_file() and not Path('/usr/bin/wsh').is_symlink()
assert Path('/usr/libexec/wsh/wsh-runtime').is_file()
assert Path('/usr/share/wsh/functions/compinit').is_file()
assert not Path('/usr/libexec/wsh/bin').exists()
run('rpm', '-V', 'wsh')
assert run('rpm', '-q', '--qf', '%{LICENSE}', 'wsh') == 'MIT AND MIT-Modern-Variant AND ISC AND GPL-2.0-only AND BSD-3-Clause'
file_flags = run('rpm', '-q', '--qf', '[%{FILENAMES}\t%{FILEFLAGS:fflags}\n]', 'wsh')
licenses = {Path(name).name for name, flags in (line.split('\t') for line in file_flags.splitlines()) if 'l' in flags}
assert licenses == {'WSH-MIT', 'ZSH', 'TOMLC17-MIT', 'AUTOSUGGESTIONS-MIT',
                    'HIGHLIGHTING-BSD', 'ZSH-Z-MIT', 'OMZ-MIT', 'GPL-2.0-only', 'OPENSSH-ISC'}, licenses
provides = set(run('rpm', '-q', '--provides', 'wsh').splitlines())
assert {
    'bundled(tomlc17) = 0^20260822git64a063b',
    'bundled(zsh-autosuggestions) = 0.7.1',
    'bundled(zsh-history-substring-search) = 1.1.0^20260115git14c8d2e',
    'bundled(zsh-syntax-highlighting) = 0.8.1~20260822git2fc57d6',
    'bundled(zsh-z) = 2.0^20260901git9112b53',
} <= provides, provides
for shell in ('/usr/bin/wsh', '/bin/wsh'):
    assert Path('/etc/shells').read_text().splitlines().count(shell) == 1
assert expected_source in run('/usr/bin/wsh', '--wsh-version')
assert run('rpm', '-q', '--qf', '%{VERSION}-%{RELEASE}', 'wsh') == expected_release
print('PASS: hosted RPM layout, inventory, license tags, bundled dependencies, source identity and registration')
