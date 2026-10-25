# Wsh 0.4.8 publication

Wsh 0.4.8 is released on GitHub, [COPR](https://copr.fedorainfracloud.org/coprs/wakamex/wsh/) and the [Homebrew](https://brew.sh/) tap `wakamex/tap`, all from the same tagged commit. It is the first release with a source archive and a Homebrew formula, and it builds and tests on macOS and Ubuntu. The GitHub Release passed both canonical builds, which now also agree on the source archive, and attestation. The COPR package was built from the tag with networking disabled, then upgraded from 0.4.7, freshly installed, logged into and removed in a disposable Fedora 44 virtual machine with signature checking enabled. The formula installed from the live tap and passed `brew test` on a clean macOS runner.

## Results

| Check | Result |
| --- | --- |
| Source and CI | Annotated tag `v0.4.8` resolves to `7caddc4314d7a530fb5e16f1c3c86e2f03916936`, which was remote main when tagged. [Run 40236950009](https://github.com/wakamex/wsh/actions/runs/40236950009) passed `release-eligible / validate` on its first attempt, including the macOS, Ubuntu and Homebrew formula jobs |
| GitHub Release | [Publish run 40238080664](https://github.com/wakamex/wsh/actions/runs/40238080664) passed validation, tag validation, two canonical builds, comparison of the RPM, manifest and source archive, attestation and public verification. The [immutable release](https://github.com/wakamex/wsh/releases/tag/v0.4.8) carries the committed notes |
| COPR source | Built in a clean worktree at the tag, where `git describe --exact-match --tags` printed `v0.4.8`. The tagged `tests/source-rpm.py` passed before submission |
| COPR rebuild | [Build 11206568](https://copr.fedorainfracloud.org/coprs/build/11206568/) passed with networking disabled and full `%check`. Reference and native upstream suites each passed 75 scripts with zero failures and two skips; the complete installed suite passed, including the type-ahead and symlinked-start tests |
| Signed DNF upgrade | `0.4.7-1.fc44` upgraded to `0.4.8-1.fc44`; package signatures, digests, source identity, installed paths, licenses, bundled declarations and `rpm -V` passed |
| Installed catalog | All 31 installed snapshot files match their SHA-256 names, and every one of the 32 references in the generated `catalog.zsh` resolves to one |
| Installed regressions | As root, the interrupt and `WSH_VERSION` tests passed; as an unprivileged user, the signed package passed the re-source test, 33 history checks, 3 mail-notice checks, the four terminal-doctor cases, 40 interactive-default checks, 5 directory-report checks, the type-ahead test and the symlinked-start test |
| Fresh install and login | Fresh DNF installation, authenticated unprivileged `chsh`, serial getty/PAM login and job control passed |
| Removal and recovery | Removal deleted executables and shell registrations while preserving account records. The recovery account restored Bash and verified login; the VM was shut down |
| Homebrew tap | `Formula/wsh.rb`, rendered by the tag's `packaging/homebrew/sync-tap.zsh` with the source archive's digest from the Release's `SHA256SUMS`, is tap commit `05e1561`. [Run 40240214614](https://github.com/wakamex/wsh/actions/runs/40240214614) installed it with `brew install wakamex/tap/wsh` on a clean macOS 15 runner and passed `brew test` |

## Package identity

| Item | Value |
| --- | --- |
| Signed RPM SHA-256 | `1f3afe5cc81f15aa4ec926d37aac5e1c382448c872c80ded764309415a1ac7b2` |
| Installed Wsh SHA-256 | `3f15ebc1f154d804df2f59d61b4370b153cba10849194b5b48cb37ed0add1c50` |
| Installed manifest SHA-256 | `ae8c17664c7ea5e295e1b0047f478837ed1e6513f441270df9e0265a1fab8c2e` |
| Source RPM SHA-256 | `dda924b68654d9913c87f368f6fec7ef413f04d4c12ef790e4375aceb9665dfd` |
| Source archive SHA-256 | `a731e85be0a5ad8c00e1d90f5a90174f15e07790feb0b9fc560ddbb6e2df29f0` |
| Signing key fingerprint | `69A9B67B68983B6F064E499E6A3CFDF5066D9E4E` |

## Evidence and scope

[Evidence](evidence.tar.gz) retains CI, publish, tap-verification and COPR records, the tag check, build logs, the source RPM build log and hash, the published formula and tap commits, exact guest scripts and logs, the installed manifest, regression outputs and the login transcript. [Identity](identity.json) records accepted gates and hashes; `SHA256SUMS` covers retained files. Package-signature checking remained enabled throughout, and SELinux was enforcing in every guest step. No reboot test was run: the release does not change the package scripts or shell registration that a reboot exercises. The tap's first push was committed by hand from the tag script's rendered formula, unchanged, because the script's temporary clone had no Git identity; main's `sync-tap.zsh` now sets it.
