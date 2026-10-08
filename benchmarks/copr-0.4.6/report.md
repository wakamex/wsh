# Wsh 0.4.6 publication

Wsh 0.4.6 is released on GitHub and COPR from the same tagged commit. It keeps Enter and Space working after re-sourcing a configuration that loads zsh-autosuggestions, searches history with Up and Down in every terminal key mode, and sets `WSH_VERSION` for startup files. The GitHub Release passed both canonical builds, attestation and public verification. The COPR package was built from the tagged commit, and in a disposable Fedora VM with SELinux enforcing it passed these checks: the signed upgrade from `0.4.5`, the installed catalog, the interrupt, `WSH_VERSION`, re-source, history, mail and terminal-doctor regressions, fresh installation, login with job control, and removal with recovery.

## Results

| Check | Result |
| --- | --- |
| Source and CI | Annotated tag `v0.4.6` resolves to `9195d8fe25d2b47ebf94c4b625c14ff77e3db82b`, which was remote main when tagged. [Run 37728119497](https://github.com/wakamex/wsh/actions/runs/37728119497) passed `release-eligible / validate` on its first attempt |
| GitHub Release | [Publish run 37729100152](https://github.com/wakamex/wsh/actions/runs/37729100152) passed validation, tag validation, two canonical builds, comparison and attestation, and public verification. The [immutable release](https://github.com/wakamex/wsh/releases/tag/v0.4.6) carries the committed notes |
| COPR source | Built in a clean worktree at the tag, where `git describe --exact-match --tags` printed `v0.4.6`. The tagged `tests/source-rpm.py` passed before submission |
| COPR rebuild | [Build 11091886](https://copr.fedorainfracloud.org/coprs/build/11091886/) passed with networking disabled and full `%check`. Reference and native upstream suites each passed 75 scripts with zero failures and two skips; the complete installed suite passed, including the re-source, `WSH_VERSION`, history search and interrupt tests |
| Signed DNF upgrade | `0.4.5-1.fc44` upgraded to `0.4.6-1.fc44`; package signatures, digests, source identity, installed paths, licenses, bundled declarations and `rpm -V` passed |
| Installed catalog | All 30 installed snapshot files match their SHA-256 names, and every reference in the generated `catalog.zsh` resolves to one |
| Installed regressions | The installed interrupt and `WSH_VERSION` tests passed; as an unprivileged user, the signed package passed the re-source test, 33 history checks, 3 mail-notice checks and the four terminal-doctor cases |
| Fresh install and login | Fresh DNF installation, authenticated unprivileged `chsh`, serial getty/PAM login and job control passed |
| Removal and recovery | Removal deleted executables and shell registrations while preserving account records. The recovery account restored Bash and verified login; the VM was shut down |

## Package identity

| Item | Value |
| --- | --- |
| Signed RPM SHA-256 | `c40b169fa824f03a0126ea5c48a5763b625dfbef333c976235288d3182dac350` |
| Installed Wsh SHA-256 | `5bc1a8c67c1e6206652c92635a9b2db41509ab54c5afe6bed419745a4ec60553` |
| Installed manifest SHA-256 | `9225ba6538030ca65d6c2c87cb7c7e6509052842fe3fc1d309206ec0e7bef516` |
| Source RPM SHA-256 | `057dbe97d7ca0dae9fa44b5fb83dfcc691cf5459e0004f06e78e406279288eef` |
| Signing key fingerprint | `69A9B67B68983B6F064E499E6A3CFDF5066D9E4E` |

## Evidence and scope

[Evidence](evidence.tar.gz) retains CI, publish and COPR records, the tag check, build logs, the source inventory and integrity check, signing checks, exact guest scripts and logs, the installed manifest, regression outputs and the login transcript. [Identity](identity.json) records accepted gates and hashes; `SHA256SUMS` covers retained files. Package-signature checking remained enabled throughout. Normal shell startup and package layout did not change, so reboot qualification was not repeated.
