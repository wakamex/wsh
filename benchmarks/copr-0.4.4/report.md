# Wsh 0.4.4 publication

Wsh 0.4.4 is released on GitHub and COPR from the same tagged commit. It recognizes the `z` plugin in the latest Oh My Zsh as an official copy. The GitHub Release passed both canonical builds, attestation and public verification; the COPR package was built from the tagged commit, and its signed upgrade from `0.4.3`, the installed catalog, history, mail and terminal-doctor regressions, fresh installation, login with job control and removal with recovery passed in a disposable Fedora VM with SELinux enforcing.

## Results

| Check | Result |
| --- | --- |
| Source and CI | Annotated tag `v0.4.4` resolves to `bf3d735d67f98811c04cfbf2ea9f9eb8374133ca`, which matched remote main. [Run 37504436596](https://github.com/wakamex/wsh/actions/runs/37504436596) passed `release-eligible / validate` on its first attempt |
| GitHub Release | [Publish run 37505951407](https://github.com/wakamex/wsh/actions/runs/37505951407) passed validation, tag validation, two canonical builds, comparison and attestation, and public verification. The [immutable release](https://github.com/wakamex/wsh/releases/tag/v0.4.4) carries the committed notes |
| COPR source | Built in a clean worktree at the tag, where `git describe --exact-match --tags` printed `v0.4.4`. `tests/source-rpm.py` passed before submission |
| COPR rebuild | [Build 11085788](https://copr.fedorainfracloud.org/coprs/build/11085788/) passed with networking disabled and full `%check`. Reference and native upstream suites each passed 75 scripts with zero failures and two skips; the complete installed suite passed, including the plugin-catalog and Git handoff matrices and the 44 Git provenance cases |
| Signed DNF upgrade | `0.4.3-1.fc44` upgraded to `0.4.4-1.fc44`; package signatures, digests, source identity, installed paths, licenses, bundled declarations and `rpm -V` passed |
| Installed catalog | The package installs the `d745fbf` `z` snapshot with matching SHA-256, and the generated `catalog.zsh` references it |
| Installed regressions | As an unprivileged user, the signed package passed 33 history checks, 3 mail-notice checks and the four terminal-doctor cases |
| Fresh install and login | Fresh DNF installation, authenticated unprivileged `chsh`, serial getty/PAM login and job control passed |
| Removal and recovery | Removal deleted executables and shell registrations while preserving account records. The recovery account restored Bash and verified login; the VM was shut down |

## Package identity

| Item | Value |
| --- | --- |
| Signed RPM SHA-256 | `1a05eadd55788c134a0b2e36beb9921dc559d6b8bc62076217b7c9ab70d88266` |
| Installed Wsh SHA-256 | `688cd6cfb16515d90070419ac323a4be9cba4c6d24f0cd7e629cd6afc6114ffe` |
| Installed manifest SHA-256 | `90788d4c6cf5862e06a76ef1f4ce8ce3ddb41f848b398a9413d7140ccf0a71c2` |
| Source RPM SHA-256 | `e7dc4681fe6d189b339db853e1627859a91dbaa2268954740469f2ef3e7bddfa` |
| Signing key fingerprint | `69A9B67B68983B6F064E499E6A3CFDF5066D9E4E` |

## Evidence and scope

[Evidence](evidence.tar.gz) retains CI, publish and COPR records, the tag check, build logs, the source inventory and integrity check, signing checks, exact guest scripts and logs, the installed manifest, regression outputs and the login transcript. [Identity](identity.json) records accepted gates and hashes; `SHA256SUMS` covers retained files. Package-signature checking remained enabled throughout. The [catalog qualification](../plugin-catalog-omz-d745fbf-2026-10-06/report.md) records the handoff matrix and startup measurement for the new entry. Normal shell startup and package layout did not change, so reboot qualification was not repeated.
