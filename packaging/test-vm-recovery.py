#!/usr/bin/env python3
"""Run account-state and optional-resource failures against the installed RPM."""
import json
from pathlib import Path
import subprocess
import sys
from vm import WORK, run

results = []
cases = {
    'state-corrupt': "mkdir -p /home/shellempty/.local/share/wsh; printf '{broken' > /home/shellempty/.local/share/wsh/bundle-state.json",
    'state-unreadable': 'chmod 000 /home/shellempty/.local/share/wsh/bundle-state.json',
    'state-incompatible': "chmod 644 /home/shellempty/.local/share/wsh/bundle-state.json; printf '{\"schema_version\":999}' > /home/shellempty/.local/share/wsh/bundle-state.json",
    'runtime-missing': 'mv /usr/libexec/wsh/bin/wsh-runtime /var/tmp/wsh-runtime-backup',
    'runtime-unreadable': 'chmod 000 /usr/libexec/wsh/bin/wsh-runtime',
    'runtime-incompatible': "mv /usr/libexec/wsh/bin/wsh-runtime /var/tmp/wsh-runtime-backup; printf '#!/bin/sh\\nexit 64\\n' > /usr/libexec/wsh/bin/wsh-runtime; chmod 755 /usr/libexec/wsh/bin/wsh-runtime; restorecon /usr/libexec/wsh/bin/wsh-runtime",
    'integration-missing': 'mv /usr/libexec/wsh/share/wsh /var/tmp/wsh-integration-backup',
}
for name, setup in cases.items():
    run('set -e\n' + setup + '\n', name + '-setup')
    # Exercise runtime startup through a shell-local selector in the fixture.
    if name.startswith('runtime-'):
        run("printf 'WSH_THEME=minimal\\n' > /home/shellempty/.zshrc; chown shellempty:shellempty /home/shellempty/.zshrc\n", name + '-theme')
    try:
        subprocess.run([sys.executable, str(Path(__file__).with_name('test-login.py')), name, 'shellempty'], check=True)
        results.append({'case': name, 'pam_tty_login': True})
    finally:
        run('''set -e
if [ -f /var/tmp/wsh-runtime-backup ]; then mv -f /var/tmp/wsh-runtime-backup /usr/libexec/wsh/bin/wsh-runtime; fi
chmod 755 /usr/libexec/wsh/bin/wsh-runtime
if [ -d /var/tmp/wsh-integration-backup ]; then mv /var/tmp/wsh-integration-backup /usr/libexec/wsh/share/wsh; fi
rm -f /home/shellempty/.zshrc
restorecon -R /usr/libexec/wsh
rpm -V wsh
''', name + '-restore')
    (WORK / 'recovery-results.json').write_text(json.dumps(results, indent=2) + '\n')
print('PASS: seven real PAM login failures preserve native shell availability')
