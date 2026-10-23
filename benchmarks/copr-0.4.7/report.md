# Wsh 0.4.7 publication

Wsh 0.4.7 is released on GitHub and [COPR](https://copr.fedorainfracloud.org/coprs/wakamex/wsh/) from the same tagged commit. It works without a framework, setting up completion, editing keys and history clean-up when startup files do not; refreshes a stale Git index in the background after a slow prompt status; and reports the directory of a `wsh --run` command correctly to the terminal. The GitHub Release passed both canonical builds, attestation and public verification. The COPR package was built from the tagged commit with networking disabled, then upgraded from 0.4.6, freshly installed, logged into and removed in a disposable Fedora 44 virtual machine with signature checking enabled.

## Results

| Check | Result |
| --- | --- |
| Source and CI | Annotated tag `v0.4.7` resolves to `d19bdb54d07e8014c39966605029838579b5e282`, which was remote main when tagged. [Run 40027586165](https://github.com/wakamex/wsh/actions/runs/40027586165) passed `release-eligible / validate` on its first attempt |
| GitHub Release | [Publish run 40029064154](https://github.com/wakamex/wsh/actions/runs/40029064154) passed validation, tag validation, two canonical builds, comparison and attestation, and public verification. The [immutable release](https://github.com/wakamex/wsh/releases/tag/v0.4.7) carries the committed notes |
| COPR source | Built in a clean worktree at the tag, where `git describe --exact-match --tags` printed `v0.4.7`. The tagged `tests/source-rpm.py` passed before submission |
| COPR rebuild | [Build 11199822](https://copr.fedorainfracloud.org/coprs/build/11199822/) passed with networking disabled and full `%check`. Reference and native upstream suites each passed 75 scripts with zero failures and two skips; the complete installed suite passed, including the interactive-defaults, directory-report and index-refresh tests |
| Signed DNF upgrade | `0.4.6-1.fc44` upgraded to `0.4.7-1.fc44`; package signatures, digests, source identity, installed paths, licenses, bundled declarations and `rpm -V` passed |
| Installed catalog | All 31 installed snapshot files match their SHA-256 names, and every one of the 32 references in the generated `catalog.zsh` resolves to one |
| Installed regressions | As root, the interrupt and `WSH_VERSION` tests passed; as an unprivileged user, the signed package passed the re-source test, 33 history checks, 3 mail-notice checks, the four terminal-doctor cases, 40 interactive-default checks and 5 directory-report checks |
| Fresh install and login | Fresh DNF installation, authenticated unprivileged `chsh`, serial getty/PAM login and job control passed |
| Removal and recovery | Removal deleted executables and shell registrations while preserving account records. The recovery account restored Bash and verified login; the VM was shut down |

## Package identity

| Item | Value |
| --- | --- |
| Signed RPM SHA-256 | `1b89a4b809ccf76d8cdbf86f7a34a161e04d8065dc98d7e1a76f67049ad0dcfa` |
| Installed Wsh SHA-256 | `578afda20c25349d4e12f1cdc8c09b8e62d89a8c486b1d9c697d7f721be5f850` |
| Installed manifest SHA-256 | `bc26d403cb2a28b0788ad5292e8907babe3f470c2bb0aeaeb0f41c331a4c7f1d` |
| Source RPM SHA-256 | `5b301fb2b11131271d16303b3548f69cda18932fa1d8b9810461cd7f8192f5e9` |
| Signing key fingerprint | `69A9B67B68983B6F064E499E6A3CFDF5066D9E4E` |

## Evidence and scope

[Evidence](evidence.tar.gz) retains CI, publish and COPR records, the tag check, build logs, the source RPM build log and hash, exact guest scripts and logs, the installed manifest, regression outputs and the login transcript. [Identity](identity.json) records accepted gates and hashes; `SHA256SUMS` covers retained files. Package-signature checking remained enabled throughout, and SELinux was enforcing in every guest step. No reboot test was run: this release changes interactive startup, which the login and installed tests cover, but not the package scripts or shell registration that a reboot exercises.
