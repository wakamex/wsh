# Fedora 44 COPR installation qualification

Wsh now supports repository-backed installation and ordinary DNF updates on Fedora 44 x86-64. The hosted package passed fresh installation, upgrade from the public v0.4.0 RPM, authenticated shell selection, real login, job control, reboot and removal. Tests used the actual COPR repository in a disposable Fedora VM with SELinux enforcing and an independent recovery account.

## Results

| Check | Result |
| --- | --- |
| Public source identity | SRPM generated from clean, public commit `2bd3924e57f2b7e1f8726972cd4406b44c21fb77`; GitHub source archive matched the checkout and SRPM integrity checks passed |
| Required main-push CI | `release-eligible / validate` passed for that exact commit in [run 34747760017](https://github.com/wakamex/wsh/actions/runs/34747760017), including the glibc 2.28 installed suite and offline Fedora source rebuild |
| COPR source rebuild | [Build 10981201](https://copr.fedorainfracloud.org/coprs/build/10981201/) succeeded for `fedora-44-x86_64` with build networking disabled; reference and native upstream suites each reported 75 successful scripts, zero failures and two skips; the complete installed Wsh suite passed after RPM processing |
| Repository and signatures | The generated repository uses HTTPS, `gpgcheck=1` and `repo_gpgcheck=0`. DNF imported the COPR project key and verified the package; a separate `rpmkeys --checksig -v` check passed both signatures and the header/payload digests |
| Upgrade | `dnf --refresh upgrade wsh` replaced the public `0.4.0-0.1` package with hosted `0.4.0-1.fc44`; source identity, standard installed paths, licenses, bundled dependency declarations, `rpm -V` and exact `/etc/shells` registrations passed |
| Actual login and job control | Serial getty/PAM login passed after upgrade, after reboot and after fresh installation. Each run checked prompt readiness, Ctrl-Z, `fg`, child resumption, Ctrl-C and status 130 |
| Fresh install and account selection | DNF removal followed by `dnf install wsh` succeeded. An unprivileged account authenticated through real `chsh` and selected registered `/usr/bin/wsh` |
| Removal and recovery | DNF removed the executable/helper and both shell registrations. Removal also succeeded with the disposable account still referencing Wsh, leaving its account record unchanged. The independent recovery account restored Bash and verified login |

## Package identity

| Item | Value |
| --- | --- |
| Package | `wsh-0.4.0-1.fc44.x86_64` |
| Signed RPM SHA-256 | `76261ae33549923eaf2c52d3b86874a12c820551a34b254baff759e53ff378dc` |
| COPR project key fingerprint | `69A9B67B68983B6F064E499E6A3CFDF5066D9E4E` |
| Installed Wsh SHA-256 | `b5e9c15aeab5248f3d82be960e1b4493b6385b15e21e1308c32abcb3dc1c39d0` |
| Installed manifest SHA-256 | `a250a40f8b3fb099cee4e59f0593221004cd28ffd6663ef8f0d2ac13029c996b` |
| Build compiler | GCC 16.2.1, Fedora normal flags and RPM post-processing |
| Zsh source | `cad0d67c76e2be7371cf3526b79ea2581810d35a`, with the selected Wsh patches |

This Fedora rebuild has its own build identity and dependency requirements. It does not inherit the canonical GitHub RPM's glibc 2.28 qualification or GitHub attestation. No new GitHub version tag was created for this packaging update. Login coverage is real TTY/PAM, not a complete graphical GDM session.

## Method and retained evidence

The fixed gate was a successful exact-commit CI run and COPR source build, followed by actual signed-repository package transactions and login checks. Package-signature verification stayed enabled. No Wsh implementation change was needed. COPR's source preparation and import queues delayed the run before compilation began; no duplicate build was submitted.

The VM used the existing disposable Fedora fixture with an independent recovery account. Its launch command, backing image identity, effective repository configuration, exact guest scripts, transcripts and test results are in [the evidence archive](evidence.tar.gz). The archive also retains the COPR build/root/backend logs, API identities, source inventory, installed manifest, public signing key and current-source/SRPM checks. [Machine-readable identity](identity.json) records the archive digest and accepted gates; `SHA256SUMS` inside the archive covers each retained input. No RPM binaries, private keys or VM images are included.

The public v0.4.0 baseline reached login but failed the current test's executable-path assertion because it resolves to `/usr/libexec/wsh/bin/wsh`. A retained baseline-only copy changed that expected path and passed login/job control. All COPR login runs used the unchanged current test and required `/usr/bin/wsh`. Each upgrade login started a new shell, following the documented [layout restart boundary](../../packaging/FEDORA-REVIEW.md#upgrade-boundary).

The retained guest scripts drive `dnf copr enable`, `dnf upgrade`, `dnf install`, `dnf remove` and `rpmkeys` through [the VM runner](../../packaging/vm.py). [The login test](../../packaging/test-login.py) talks to serial getty; the existing authenticated [chsh test](../../packaging/test-chsh-guest.py) runs inside the guest. The VM was restored to Bash without Wsh installed and shut down after qualification.
