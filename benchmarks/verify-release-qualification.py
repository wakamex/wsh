#!/usr/bin/env python3
"""Verify retained independent RPM builds and actual Fedora QEMU qualification."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

root = Path(__file__).resolve().parents[1]
evidence = root/'benchmarks/release-qualification-2026-09-10'
identity = json.loads((evidence/'identity.json').read_text())
sha = lambda data: hashlib.sha256(data).hexdigest()
archives = {}
for kind in ('build', 'vm'):
    record = identity[kind]
    path = evidence/(kind+'-results.tar.gz')
    assert sha(path.read_bytes()) == record['sha256'], kind
    with tarfile.open(path) as archive:
        files = {member.name: archive.extractfile(member).read() for member in archive.getmembers()}
    assert set(files) == set(record['files']), kind
    for name, digest in record['files'].items():
        assert sha(files[name]) == digest, name
    archives[kind] = files
build, vm = archives['build'], archives['vm']
for name, digest in identity['sources'].items():
    data = (root/name).read_bytes()
    if sha(data) != digest:
        data = vm.get('current-tests/'+name)
        if data is None:
            data = subprocess.check_output(['git', 'show', identity['source_revision']+':'+name], cwd=root)
    assert sha(data) == digest, name
for name, digest in (('manifest.json', identity['manifest_sha256']), ('package.rpm', identity['rpm_sha256'])):
    assert build['a/'+name] == build['b/'+name]
    assert sha(build['a/'+name]) == digest
manifest = json.loads(build['a/manifest.json'])
assert manifest['status'] == 'release' and manifest['source_revision'] == identity['source_revision']
assert manifest['requirements']['minimum_glibc'] == '2.28'
assert vm['guest-results/installed-manifest.json'] == build['a/manifest.json']
for worker in ('a', 'b'):
    log = build['build-'+worker+'.log']
    for marker in (b'PASS: installed label', b'PASS: installed native main ownership', b'plugin-git-handoff passed',
                   b'PASS: actual ZLE history', b'PASS: 13 real ZLE completion/cache', b'PASS: real RPM agreement'):
        assert marker in log, (worker, marker)
assert len(identity['login_cases']) == 21
assert sum(case['job_control'] for case in identity['login_cases'].values()) == 11
for name, case in identity['login_cases'].items():
    assert json.loads(vm[name+'.json']) == case and case['pam_tty_login']
    transcript = vm[name+'.bin']
    assert b'VM_LOGIN:5.9.999.3-test:/usr/bin/wsh:/usr/libexec/wsh/bin/wsh' in transcript
    if case['job_control']:
        assert b'CHILD_RESUMED\r\n' in transcript and b'JOB_STATUS:130' in transcript
assert b'user_u:user_r:user_t:' in vm['post-reboot-confined.bin']
assert len(json.loads(vm['recovery-results.json'])) == 7
assert all(case['pam_tty_login'] for case in json.loads(vm['recovery-results.json']))
assert vm['guest-results/boot-before'] != vm['guest-results/boot-after']
assert sha(vm['wsh-legacy']) == json.loads(vm['legacy-identity.json'])['sha256']
assert json.loads(vm['guest-results/account-migration.json'])['passed']
assert all(case['passed'] for case in json.loads(vm['guest-results/private-migration/results.json']))
assert b'Wsh is still a local account shell' in vm['guest-results/removal-guard.log']
assert b'Enforcing' in vm['final-guest.log'] and b'PASS: native installation inventory' in vm['final-guest.log']
assert json.loads(vm['image/image.json'])['sha256'] == identity['image_sha256']
assert b'Good signature' in vm['image/image-verification.log']
assert b'(release build)' in vm['after-reboot.log']
print('PASS: independent release-mode RPM bytes, 21 QEMU PAM logins, 11 job-control cases, migration, recovery and reboot')
