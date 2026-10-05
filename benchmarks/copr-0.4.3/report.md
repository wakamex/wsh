# COPR 0.4.3 publication

Wsh `0.4.3-1.fc44` is available through COPR for Fedora 44 x86-64. The signed package recovers history saving after a shell is killed while saving, lets a shell exiting during another shell's save wait for it instead of losing the history it saves on exit, and announces unread mail once instead of at every mail check. DNF upgrade from `0.4.2`, the installed history, mail and terminal-doctor regressions, fresh installation, login with job control and removal with recovery passed in a disposable Fedora VM with SELinux enforcing.

## Results

| Check | Result |
| --- | --- |
| Source and CI | Clean public commit `b30c880550843ef4e07d3658e85227b88d553a37` matched remote main. [Run 37321122202](https://github.com/wakamex/wsh/actions/runs/37321122202) passed `release-eligible / validate` on its first attempt |
| Source RPM integrity | `tests/source-rpm.py` passed real sources, dependencies, build and check phases, absence of prebuilt payload and offline source integrity. It ran after submission, against the same SRPM bytes |
| COPR rebuild | [Build 11078840](https://copr.fedorainfracloud.org/coprs/build/11078840/) passed with networking disabled and full `%check`. Reference and native upstream suites each passed 75 scripts with zero failures and two skips; the complete installed suite passed, including 33 history and 3 mail checks |
| Signed DNF upgrade | `0.4.2-1.fc44` upgraded to `0.4.3-1.fc44`; package signatures, digests, source identity, installed paths, licenses, bundled declarations and `rpm -V` passed |
| Installed regressions | As an unprivileged user, the signed package passed 33 history checks, including stale symlink and file locks and the fresh-lock exit wait, 3 mail-notice checks, and the four terminal-doctor cases |
| Fresh install and login | Fresh DNF installation, authenticated unprivileged `chsh`, serial getty/PAM login and job control passed |
| Removal and recovery | Removal deleted executables and shell registrations while preserving account records. The recovery account restored Bash and verified login; the VM was shut down |

## Package identity

| Item | Value |
| --- | --- |
| Signed RPM SHA-256 | `43b627375ff3cc20b3eb82089b20d431f651a8cebb69eba53b1ecfa03fbaeddc` |
| Installed Wsh SHA-256 | `d4a79f111b4f91358434ecb3090f0acd5b55135deff4b2450369466e8cd54a1c` |
| Installed manifest SHA-256 | `8158afec9035dca3c03efd0aaf985591453cbddd33a89f2b6db5944bec1cc225` |
| Source RPM SHA-256 | `9595411ebd3408cacd56b876b2c64ab5cc14a1c7c581c3dec4f035acf4a3125d` |
| Signing key fingerprint | `69A9B67B68983B6F064E499E6A3CFDF5066D9E4E` |

## Evidence and scope

[Evidence](evidence.tar.gz) retains CI and COPR records, build logs, the source inventory and integrity check, effective repository configuration, signing checks, exact guest scripts and logs, the installed manifest, regression outputs and the login transcript. [Identity](identity.json) records accepted gates and hashes; `SHA256SUMS` covers retained files. Package-signature checking remained enabled throughout.

The first baseline script installed and verified `0.4.2-1.fc44` but stopped when replacing older test copies in the guest's `/var/tmp`, which Fedora's protected-regular rule forbids for files owned by another user; `copr043-stage.sh` replaced them and recorded their hashes before the upgrade. The [bug record](../../UPSTREAM-ZSH-BUGS.md#monotonic-clock-compared-with-file-times) covers the defects and their reproducers. A real Wakterm multiplexer restart on the development build left no history lock and kept pane-first recall. Normal shell startup and package layout did not change, so reboot qualification was not repeated. No GitHub version tag was created.
