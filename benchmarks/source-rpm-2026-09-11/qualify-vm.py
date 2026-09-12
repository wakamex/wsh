#!/usr/bin/env python3
"""Qualify a rebuilt RPM in the already prepared disposable Fedora guest."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
rpm = Path(sys.argv[1]).resolve()
work = Path(os.environ['WSH_VM_WORK'])
spec = importlib.util.spec_from_file_location('vm', ROOT/'packaging/vm.py')
vm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vm)
scp = ['scp','-o','BatchMode=yes','-o','UserKnownHostsFile='+str(work/'known_hosts'),'-i',str(work/'id_ed25519'),'-P','22284']
subprocess.run(scp+[str(rpm),str(ROOT/'build/native_manifest.py'),str(ROOT/'packaging/test-chsh-guest.py'),'recovery@127.0.0.1:/var/tmp/'],check=True)
vm.run('''set -eu
dnf -y install /var/tmp/wsh-*.x86_64.rpm
rpm -V wsh
python3 /var/tmp/native_manifest.py verify /usr/libexec/wsh
/usr/bin/wsh --version
/usr/bin/wsh --wsh-version
grep -qxF /usr/bin/wsh /etc/shells
grep -qxF /bin/wsh /etc/shells
python3 /var/tmp/test-chsh-guest.py
rpm -qa | sort
cat /proc/sys/kernel/random/boot_id
getenforce
''','install')
def login(name):
    subprocess.run(['python3',ROOT/'packaging/test-login.py',name,'shellempty','--job-control'],check=True)
login('empty-home-login')
vm.run('''set -eu
if rpm -e wsh; then echo 'unexpected removal'; exit 1; fi
rpm -V wsh
printf 'export WSH_THEME=minimal\n' > /home/shellempty/.zshrc
chown shellempty:shellempty /home/shellempty/.zshrc
''','removal-guard')
login('theme-login')
before = vm.run('cat /proc/sys/kernel/random/boot_id','boot-before').stdout.strip()
vm.run('systemd-run --on-active=2 /usr/bin/systemctl reboot','reboot')
time.sleep(5)
for attempt in range(60):
    result = vm.run('cat /proc/sys/kernel/random/boot_id','boot-after',expected=None)
    if result.returncode == 0 and result.stdout.strip() != before: break
    time.sleep(1)
else: raise AssertionError('guest did not reboot')
login('post-reboot-login')
vm.run('''set -eu
rpm -V wsh
python3 /var/tmp/native_manifest.py verify /usr/libexec/wsh
cat /usr/libexec/wsh/manifest.json
getenforce
chsh -s /bin/bash shellempty
rpm -e wsh
! test -e /usr/bin/wsh
! grep -qxF /usr/bin/wsh /etc/shells
! grep -qxF /bin/wsh /etc/shells
getent passwd recovery
''','final-removal')
(work/'result.json').write_text(json.dumps(dict(install=True,inventory=True,chsh=True,pam_logins=3,job_control=3,reboot=True,removal_guard=True,removal=True),indent=2)+'\n')
vm.run('systemd-run --on-active=2 /usr/bin/systemctl poweroff','shutdown')
print('PASS: source-built RPM installation, inventory, chsh, three PAM/job-control sessions, reboot and removal')
