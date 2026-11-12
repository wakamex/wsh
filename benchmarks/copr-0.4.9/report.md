# Wsh 0.4.9 publication

Wsh 0.4.9 is released on GitHub, [COPR](https://copr.fedorainfracloud.org/coprs/wakamex/wsh/) and the [Homebrew](https://brew.sh/) tap `wakamex/tap`, all from the same tagged commit. The GitHub Release passed both canonical builds and attestation. The COPR package was built from the tag with networking disabled, then upgraded from 0.4.8, freshly installed, logged into and removed in a disposable Fedora 44 virtual machine with signature checking enabled. The formula installed from the live tap and passed `brew test` on a clean macOS runner on the second attempt; the first attempt failed one upstream Zsh timing test during the build.

The tag is on `0d2b2a2`, two commits after the `Release v0.4.9` commit `f08ce17`. Current Homebrew failed every tap install, including the published 0.4.8, with `NameError: uninitialized constant CurlDownloadStrategy::Timeout` when the formula fetched its Zsh resource inside the build process. `7bec8b7` makes the formula copy the download Homebrew verifies before the build, and `0d2b2a2` adds that fix to the release notes. `f08ce17` was never tagged.

## Results

| Check | Result |
| --- | --- |
| Source and CI | Annotated tag `v0.4.9` resolves to `0d2b2a21b738958de4531df1b9f7386dbf508629`, which was remote main when tagged. [Run 43275509167](https://github.com/wakamex/wsh/actions/runs/43275509167) passed `release-eligible / validate` on its first attempt, including the macOS, Ubuntu and Homebrew formula jobs. [Run 43270533419](https://github.com/wakamex/wsh/actions/runs/43270533419) on `f08ce17` failed twice in the Homebrew job with the `NameError` above |
| GitHub Release | [Publish run 43278095259](https://github.com/wakamex/wsh/actions/runs/43278095259) passed validation, tag validation, two canonical builds, comparison of the RPM, manifest and source archive, attestation and public verification. The [immutable release](https://github.com/wakamex/wsh/releases/tag/v0.4.9) carries the committed notes |
| COPR source | Built in a clean worktree at the tag, where `git describe --exact-match --tags` printed `v0.4.9`. The tagged `tests/source-rpm.py` passed before submission, which followed the Release's creation |
| COPR rebuild | [Build 11317906](https://copr.fedorainfracloud.org/coprs/build/11317906/) passed with networking disabled and full `%check`. Reference and native upstream suites each passed 75 scripts with zero failures and two skips; the complete installed suite passed, including the 26 background index refresh checks |
| Signed DNF upgrade | `0.4.8-1.fc44` upgraded to `0.4.9-1.fc44`; package signatures, digests, source identity, installed paths, licenses, bundled declarations and `rpm -V` passed |
| Installed catalog | All 31 installed snapshot files match their SHA-256 names, and every one of the 32 references in the generated `catalog.zsh` resolves to one |
| Installed regressions | As root, the interrupt and `WSH_VERSION` tests passed; as an unprivileged user, the signed package passed the re-source test, 33 history checks, 3 mail-notice checks, the four terminal-doctor cases, 40 interactive-default checks, 5 directory-report checks, the type-ahead test and the symlinked-start test |
| Fresh install and login | Fresh DNF installation, authenticated unprivileged `chsh`, serial getty/PAM login and job control passed |
| Removal and recovery | Removal deleted executables and shell registrations while preserving account records. The recovery account restored Bash and verified login; the VM was shut down |
| Homebrew tap | `Formula/wsh.rb`, rendered by the tag's `packaging/homebrew/sync-tap.zsh` with the source archive's digest from the Release's `SHA256SUMS`, is tap commit `fdb5d08`. [Run 43282823039](https://github.com/wakamex/wsh/actions/runs/43282823039) installed it with `brew install wakamex/tap/wsh` on a clean macOS runner. Attempt 1 failed `V14system.ztst` (74 scripts passed) during the build; the workflow retains no Zsh test output, so the failing assertion is unknown. Attempt 2 built, installed and passed `brew test` |

## Package identity

| Item | Value |
| --- | --- |
| Signed RPM SHA-256 | `283d51f1aebdbec2d36c37f0a12761071df5ee88ed56efdb59a17766b486d944` |
| Installed Wsh SHA-256 | `66ec3ef39bbc7cc7dde5959658a5a7defec7173257c17b429bceaeeba562e775` |
| Installed manifest SHA-256 | `9ab96cdc36bab8001d61747aa91d0a9ee879d10c93a877ad05dd7c7c66d008a8` |
| Source RPM SHA-256 | `f8e75b16b959fb4a8c92d7d1d4c1e8bfe9f232eaf39937d2fd7555d929693431` |
| Source archive SHA-256 | `402e7eb685aa83a952e5cf2bc4f2d9f8b4051e29589717d6c39db9bb6165b322` |
| Signing key fingerprint | `69A9B67B68983B6F064E499E6A3CFDF5066D9E4E` |

## Evidence and scope

[Evidence](evidence.tar.gz) retains CI, publish and both tap-verification records, the 0.4.8 tap failure that confirmed the Homebrew regression, the tag check, COPR build logs, the source RPM build log and hash, the published formula and tap commits, exact guest scripts and logs, the installed manifest and regression outputs, and the login transcript. [Identity](identity.json) records accepted gates and hashes; `SHA256SUMS` covers retained files. Package-signature checking remained enabled throughout, and SELinux was enforcing in every guest step. No reboot test was run: the release does not change the package scripts or shell registration that a reboot exercises. The formula runs the Zsh test suite during `brew install`, so a timing failure there fails a user's install, not only CI.
