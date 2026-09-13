#!/usr/bin/env python3
"""Run as root in a disposable Fedora container after installing the real RPM."""
from pathlib import Path
import pwd
import subprocess

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
run('useradd', '-m', '-s', '/usr/bin/wsh', 'wsh-package-test')
output = run('su', '-l', 'wsh-package-test', '-c',
             '[[ $ZSH_EXEPATH == /usr/bin/wsh ]] && '
             '[[ $fpath[1] == /usr/share/wsh/functions ]] && '
             'autoload -Uz is-at-least; is-at-least 5.9 && print PACKAGE_LOGIN_OK')
assert 'PACKAGE_LOGIN_OK' in output, output
for shell in ('/usr/bin/wsh', '/bin/wsh'):
    assert Path('/etc/shells').read_text().splitlines().count(shell) == 1
# Match Fedora Zsh: removal succeeds, changes registration, and leaves account
# policy to the administrator. This account and filesystem are disposable.
run('rpm', '-e', 'wsh')
assert not Path('/usr/bin/wsh').exists()
assert pwd.getpwnam('wsh-package-test').pw_shell == '/usr/bin/wsh'
assert '/usr/bin/wsh' not in Path('/etc/shells').read_text().splitlines()
assert '/bin/wsh' not in Path('/etc/shells').read_text().splitlines()
run('usermod', '-s', '/bin/bash', 'wsh-package-test')
assert 'RECOVERY_OK' in run('su', '-l', 'wsh-package-test', '-c', 'echo RECOVERY_OK')
print('PASS: real RPM layout, license tags, bundled dependency, PAM login, registration, removal and independent recovery')
