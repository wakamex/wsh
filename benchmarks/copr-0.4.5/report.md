# Wsh 0.4.5 publication

Wsh 0.4.5 is released on GitHub and COPR from the same tagged commit. It recognizes every `z` plugin version Oh My Zsh has bundled since October 2022 and fixes Ctrl-C at a busy prompt. The GitHub Release passed both canonical builds, attestation and public verification. The COPR package was built from the tagged commit, and in a disposable Fedora VM with SELinux enforcing it passed these checks: the signed upgrade from `0.4.4`, the installed catalog, the interrupt, history, mail and terminal-doctor regressions, fresh installation, login with job control, and removal with recovery.

## Results

| Check | Result |
| --- | --- |
| Source and CI | Annotated tag `v0.4.5` resolves to `86fca8dee6459a8d1352cbe2dbfc9b5b9efee8a1`, which was remote main when tagged. [Run 37543599953](https://github.com/wakamex/wsh/actions/runs/37543599953) passed `release-eligible / validate` on its first attempt |
| GitHub Release | [Publish run 37544652131](https://github.com/wakamex/wsh/actions/runs/37544652131) passed validation, tag validation, two canonical builds, comparison and attestation, and public verification. The [immutable release](https://github.com/wakamex/wsh/releases/tag/v0.4.5) carries the committed notes |
| COPR source | Built in a clean worktree at the tag, where `git describe --exact-match --tags` printed `v0.4.5`. `tests/source-rpm.py` passed before submission, run from main with the fix that reads the whole payload before unpacking it |
| COPR rebuild | [Build 11087116](https://copr.fedorainfracloud.org/coprs/build/11087116/) passed with networking disabled and full `%check`. Reference and native upstream suites each passed 75 scripts with zero failures and two skips; the complete installed suite passed, including the interrupt-propagation test, the autosuggestion pending-cancel lifecycle, the plugin-catalog and Git handoff matrices and the 44 Git provenance cases |
| Signed DNF upgrade | `0.4.4-1.fc44` upgraded to `0.4.5-1.fc44`; package signatures, digests, source identity, installed paths, licenses, bundled declarations and `rpm -V` passed |
| Installed catalog | All 30 installed snapshot files match their SHA-256 names, and every reference in the generated `catalog.zsh` resolves to one |
| Installed regressions | The installed interrupt-propagation test passed; as an unprivileged user, the signed package passed 33 history checks, 3 mail-notice checks and the four terminal-doctor cases |
| Fresh install and login | Fresh DNF installation, authenticated unprivileged `chsh`, serial getty/PAM login and job control passed |
| Removal and recovery | Removal deleted executables and shell registrations while preserving account records. The recovery account restored Bash and verified login; the VM was shut down |

## Package identity

| Item | Value |
| --- | --- |
| Signed RPM SHA-256 | `7cdb4dd70bca46cd1da73cdec0c3e03e2960843651731eaf64aa83fc761c7f66` |
| Installed Wsh SHA-256 | `b9dd0bac242e3d07c8c9533bb9ccdf992a2d969f83e077075359a57e7f3c2f64` |
| Installed manifest SHA-256 | `c9f302ffc4e822db01ed93fbbd4a2cc1ec7db5b1caa0188558ba1ca495c34078` |
| Source RPM SHA-256 | `57c0da2fbc1636504951ec906be6f231bcda4fb5f95491e24124741284a3775c` |
| Signing key fingerprint | `69A9B67B68983B6F064E499E6A3CFDF5066D9E4E` |

## Evidence and scope

[Evidence](evidence.tar.gz) retains CI, publish and COPR records, the tag check, build logs, the source inventory and integrity check, signing checks, exact guest scripts and logs, the installed manifest, regression outputs and the login transcript. [Identity](identity.json) records accepted gates and hashes; `SHA256SUMS` covers retained files. Package-signature checking remained enabled throughout. The [catalog qualification](../plugin-catalog-omz-z-history-2026-10-06/report.md) records the handoff matrix and startup measurement for the new entries, and the [Ctrl-C load test](../interrupt-loaded-2026-10-06/report.md) records the interrupt fixes under load. Normal shell startup and package layout did not change, so reboot qualification was not repeated.
