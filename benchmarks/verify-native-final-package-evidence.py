#!/usr/bin/env python3
"""Verify final native RPM reproducibility and real VM transaction/login evidence."""
import hashlib
import json
from pathlib import Path
import tarfile
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-qualification-2026-09-09'
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
for line in (OUT / 'package-SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert sha((ROOT / name).read_bytes()) == digest
meta = json.loads((OUT / 'package-metadata.json').read_text())
with tarfile.open(OUT / 'package-inputs.tar.gz') as a:
    for name, digest in meta['source_inputs'].items():
        assert sha(a.extractfile(name).read()) == digest
with tarfile.open(OUT / 'package-results.tar.gz') as a:
    def raw(name):
        return a.extractfile(name).read()
    def data(name):
        return json.loads(raw(name))
    results = data('package-results.json')
    assert results == meta['results']
    for key in ('rpm_sha256', 'source_archive_sha256'):
        assert len(results[key]) == 2 and len(set(results[key].values())) == 1
    assert sha(raw('tested.rpm')) == results['rpm_sha256']['a']
    assert results['before_boot_id'] != results['after_boot_id']
    for case in ('final-native-pam', 'final-confined-pam', 'final-fresh-empty-pam', 'final-post-reboot-pam', 'final-post-reboot-confined'):
        assert data('vm/'+case+'.json')['pam_tty_login']
    assert data('vm/final-native-pam.json')['job_control']
    cases = data('vm/recovery-results.json')
    assert len(cases) == 7 and all(r['pam_tty_login'] for r in cases)
    transactions = {r['case']: r for r in data('transactions/transactions.json')}
    for case in ('dnf-upgrade','dnf-downgrade','repair-interrupted-transaction','verify-repaired-package','new-shell-after-interruption'):
        assert transactions[case]['status'] == 0
    assert transactions['old-shell-after-upgrade']['module_and_helper']
    assert transactions['interrupted-after-payload-install']['status'] == -9
    assert b'Enforcing' in raw('vm/final-post-reboot.log')
    assert b'Wsh is still a local account shell' in raw('vm/final-removal-and-boundaries.log')
    assert b'RECOVERY_OK' in raw('vm/final-removal-and-boundaries.log')
    identity = data('rpm-queries.json')['identity']
    assert str(results['epoch']) in identity and 'wsh-development' in identity and 'BSD-3-Clause' in identity
print('PASS: final native RPM bytes, PAM/SELinux/reboot, optional failures and real transactions')
