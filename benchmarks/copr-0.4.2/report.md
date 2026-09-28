# COPR 0.4.2 publication

Wsh `0.4.2-1.fc44` is available through COPR for Fedora 44 x86-64. The signed package fixes doctor timing out from interactive terminals. Actual DNF upgrade from `0.4.1`, all four terminal-doctor regressions, fresh installation, login/job control and removal/recovery passed in a disposable Fedora VM with SELinux enforcing.

## Results

| Check | Result |
| --- | --- |
| Source and CI | Clean public commit `9edbaf9f72cf8966d8f9bd5cfafbc15863bd0e77` matched the public archive and remote main. [Run 36365892944](https://github.com/wakamex/wsh/actions/runs/36365892944) passed `release-eligible / validate` on its first attempt |
| COPR rebuild | [Build 11043274](https://copr.fedorainfracloud.org/coprs/build/11043274/) passed with networking disabled and full `%check`. Reference and native upstream suites each passed 75 scripts with zero failures and two skips; the complete installed suite passed |
| Signed DNF upgrade | `0.4.1-1.fc44` upgraded to `0.4.2-1.fc44`; package signatures, digests, source identity, installed paths, licenses, bundled declarations and `rpm -V` passed |
| Doctor from a real terminal | The installed signed package passed successful reporting, background-child cleanup, interruption and timeout checks as an unprivileged user, without the `setsid` workaround |
| Fresh install and login | Fresh DNF installation, authenticated unprivileged `chsh`, serial getty/PAM login, Ctrl-Z, `fg`, child resumption, Ctrl-C and status 130 passed |
| Removal and recovery | Removal deleted executables and shell registrations while preserving account records. The independent recovery account restored Bash and verified login; the VM was shut down |

## Package identity

| Item | Value |
| --- | --- |
| Signed RPM SHA-256 | `0cfda81733fe2ad8878348af5ef58611f476970dac4fa41ff5d8b16e4e55f1f6` |
| Installed Wsh SHA-256 | `588f261eda52b5a464292aa31a48b9f06b8f800e578af4abf2436839bd74d859` |
| Installed manifest SHA-256 | `0173e100882e66de579b3daa32af175596dfd03116507f032c586885487835dd` |
| Signing key fingerprint | `69A9B67B68983B6F064E499E6A3CFDF5066D9E4E` |

## Evidence and scope

[Evidence](evidence.tar.gz) retains CI and COPR records, source inventory, build logs, effective repository configuration, signing checks, exact guest scripts, installed manifest, doctor results and login transcripts. [Identity](identity.json) records accepted gates and hashes; `SHA256SUMS` covers retained files. Package-signature checking remained enabled throughout.

The [doctor investigation](../doctor-terminal-2026-09-27/report.md) records the failing packaged baseline and the fix. This publication repeats the regression against the signed RPM. Normal shell startup and package layout did not change, so reboot qualification was not repeated. No GitHub version tag was created.
