#!/usr/bin/env python3
"""Exercise the publication step through real YAML, Bash and Zsh parsers."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[1]
workflow = yaml.safe_load((ROOT/'.github/workflows/publish.yml').read_text())
step = next(s for s in workflow['jobs']['verify']['steps'] if s['name'] == 'Install and launch the public RPM')
script = step['run'][step['run'].index('podman run'):]
with tempfile.TemporaryDirectory(prefix='wsh-public-login-') as tmp:
    home = Path(tmp)
    capture = home/'capture.py'
    capture.write_text('import json,sys\nprint(json.dumps(dict(argv=sys.argv[1:],stdin=sys.stdin.read())))\n')
    env = dict(os.environ, HOME=tmp, ZDOTDIR=tmp, ZSH_VERSION='RUNNER_VALUE_MUST_NOT_EXPAND', CAPTURE=str(capture))
    recorder = 'podman() { python3 "$CAPTURE" "$@"; }\n'
    result = subprocess.run(['bash', '-euc', recorder+script], cwd=home, env=env, capture_output=True, text=True, check=True)
    assert not result.stderr
    captured = json.loads(result.stdout)
    assert captured['argv'] == ['run','--rm','--interactive','--volume',str(home)+'/public-download:/packages:ro','fedora:44','bash','-se']
    assert '$ZSH_VERSION' in captured['stdin'] and 'RUNNER_VALUE' not in captured['stdin']
    # Only container side effects are replaced. Bash parses the guest script,
    # and the real Zsh evaluates the exact login command passed through su.
    helpers = '''dnf() { [[ "$*" == '-y install util-linux /packages/*.rpm' ]]; }
useradd() { [[ "$*" == '-m -s /usr/bin/wsh wsh-test' ]]; }
su() {
  [[ $# == 4 && $1 == -l && $2 == wsh-test && $3 == -c ]] || return 91
  zsh -dfc "$4"
}
'''
    guest = subprocess.run(['bash','-se'], input=helpers+captured['stdin'], env=env, cwd=home, capture_output=True, text=True, check=True)
    assert guest.stdout == 'WSH_LOGIN_OK\n' and not guest.stderr, guest
    failure = subprocess.run(['bash','-se'], input=helpers+'su() { return 23; }\n'+captured['stdin'], env=env, cwd=home, capture_output=True, text=True)
    assert failure.returncode == 23 and not failure.stdout
print('PASS: public login YAML/Bash/Zsh argument preservation, runner isolation and failure propagation')
