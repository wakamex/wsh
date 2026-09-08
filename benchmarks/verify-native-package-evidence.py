#!/usr/bin/env python3
"""Verify retained real Fedora RPM, PAM, SELinux and transaction evidence."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-package-2026-09-08'
def sha(data): return hashlib.sha256(data).hexdigest()
for line in (OUT / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest, name
metadata = json.loads((OUT / 'metadata.json').read_text())
native = json.loads((ROOT / 'benchmarks/native-build-2026-09-08/build.json').read_text())
assert metadata['native_bundle'] == native['bundle_id']
assert metadata['native_sha256'] == native['binary_sha256']
assert metadata['runtime_sha256'] == native['matched_resources']['bin/wsh-runtime']
assert metadata['same_abi_upgrades_only'] and not metadata['full_gdm'] and not metadata['production_adopted']
assert not metadata['power_loss_during_payload']
with tarfile.open(OUT / 'inputs.tar.gz') as archive:
    for name, digest in metadata['inputs'].items():
        assert sha(archive.extractfile(name).read()) == digest, name
assert len(metadata['packages']) == 5
for package in metadata['packages']:
    assert len(package['sha256']) == 64 and package['size'] > 0
    assert '/usr/local/bin/zsh' not in package['requires'] and '\n/bin/zsh\n' not in package['requires']
    assert '/usr/libexec/wsh/bin/wsh' in package['files']
    assert 'Wsh is still a local account shell' in package['scripts']
with tarfile.open(OUT / 'results.tar.gz') as archive:
    def data(name): return archive.extractfile(name).read()
    def read(name): return json.loads(data(name))
    assert 'id_ed25519' not in archive.getnames()
    assert b'Good signature from "Fedora (44)' in data('image-verification.log')
    assert metadata['image']['sha256'].encode() in data('checksums.txt')
    for name in ('login-normalized', 'empty-home-pam', 'post-reboot-login', 'post-reboot-second', 'confined-selinux-login', 'reinstalled-login', 'pam-job-control-synchronized'):
        assert read(name + '.json')['pam_tty_login']
        assert b'VM_LOGIN:5.9.999.3-test:/usr/bin/wsh:/usr/libexec/wsh/bin/wsh' in data(name + '.bin')
    assert b'context=user_u:user_r:user_t:s0' in data('confined-selinux-login.bin')
    assert read('pam-job-control-synchronized.json')['job_control']
    assert b'JOB_STATUS:130' in data('pam-job-control-synchronized.bin')
    assert len(read('recovery-results.json')) == 7
    assert all(row['pam_tty_login'] for row in read('recovery-results.json'))
    reboot = read('reboot.json')
    assert reboot['before'] != reboot['after'] and reboot['recovery_ssh']
    transactions = {row['case']: row for row in read('transactions-results/transactions.json')}
    for name in ('dnf-upgrade', 'dnf-downgrade', 'new-shell-after-post-failure', 'new-shell-after-interruption', 'repair-interrupted-transaction', 'verify-repaired-package'):
        assert transactions[name]['status'] == 0, name
    assert transactions['old-shell-after-upgrade']['executable'].endswith(' (deleted)')
    assert transactions['old-shell-after-upgrade']['module_and_helper']
    assert transactions['rpm-pre-failure']['status'] != 0
    assert transactions['interrupted-after-payload-install']['status'] == -9
    assert b'AFTER_REFUSED_REMOVAL:5.9.999.3-test' in data('remove-guard.log')
    assert b'erase failed' in data('remove-guard.log')
    assert b'No such file or directory' in data('forced-removal-boundary.log')
    assert b'RECOVERY_ACCOUNT_USABLE' in data('forced-removal-boundary.log')
    assert b'PASS: unprivileged chsh' in data('unprivileged-chsh.log')
    assert b'Enforcing' in data('package-identities.log')
    assert b'Permission denied' in data('permission-counterfactual.log')
    assert b'EACCES' in data('module-failure-audit.log')
print('PASS: native RPM identities, real PAM/SELinux/chsh/reboot, recovery cases and bounded transaction evidence')
