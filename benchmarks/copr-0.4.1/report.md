# COPR 0.4.1 publication

Wsh `0.4.1-1.fc44` is available through COPR for Fedora 44 x86-64. Actual DNF upgrade from `0.4.0-2.fc44`, fresh installation, version output, 65 history checks and real login/job control passed in the disposable Fedora VM with SELinux enforcing. The shell implementation is unchanged from the preceding qualified package; this release advances the product version and resets the RPM release to `1`.

## Results

| Check | Result |
| --- | --- |
| Exact source | Clean public commit `c8ec27971b43f31ba311a3922bad756ba39c89c4`; remote main, public source archive and source-RPM integrity checks agreed |
| CI | [Run 36362891555](https://github.com/wakamex/wsh/actions/runs/36362891555) passed `release-eligible / validate` on attempt 2, including the glibc 2.28 installed suite and offline Fedora rebuild |
| COPR | [Build 11043222](https://copr.fedorainfracloud.org/coprs/build/11043222/) passed with networking disabled and full `%check`. Reference and native upstream suites each reported 75 successful scripts, zero failures and two skips; the complete installed suite passed |
| Signed DNF upgrade | `0.4.0-2.fc44` upgraded to `0.4.1-1.fc44`; signatures, digests, source identity, installed layout, licenses, bundled declarations and `rpm -V` passed |
| User-visible version | Installed `wsh --wsh-version` reported `wsh 0.4.1 (release build)` |
| Installed history | 30 persistent-history/session-isolation checks and 35 pane-history checks passed as an unprivileged account against the signed package |
| Fresh installation | DNF removal and installation passed, followed by authenticated unprivileged `chsh`, serial getty/PAM login, Ctrl-Z, `fg`, child resumption, Ctrl-C and status 130 |
| Cleanup | Package removal deleted the executable/helper and shell registrations while preserving the account record. The independent recovery account restored Bash and verified login; the VM was shut down |

## Package identity

| Item | Value |
| --- | --- |
| Signed RPM SHA-256 | `86fd39e920a94831d0d0487f9789ada495436e5125cf0f4b7f852adf8d78fb44` |
| Installed Wsh SHA-256 | `b9e6614c86832c3fb09a117527676d53428dafadc7e620cc9b72f66560b06066` |
| Installed manifest SHA-256 | `2e173ed552d726c768afcaa84ab2aeeaf240805ffd694823feae39d5f22f2f26` |
| Signing key fingerprint | `69A9B67B68983B6F064E499E6A3CFDF5066D9E4E` |

## Retained failures and scope

The first Fedora CI attempt failed upstream `V08zpty.ztst`: the second `hello` retained a carriage return. The test's final nonblocking read does not normalize carriage returns, unlike its two earlier reads. A timing-sensitive test failure is the working hypothesis; 100 local repetitions passed, and the failed jobs passed when rerun once on the unchanged commit. Both the original log and local results are retained. No source patch or test exclusion was applied.

The first VM login/job-control attempt timed out after Ctrl-C. A fresh-install transaction was started before that tool session returned, so that attempt is not accepted as upgrade-login evidence. After resetting serial getty, the isolated fresh-install login/job-control test passed. Its successful transcript and the failed transcript are both retained.

The [preceding package qualification](../copr-2026-09-27/report.md) covers reboot and the unchanged startup implementation. Reboot was not repeated for this version-only update. No GitHub version tag was created. Real Wakterm mux-restart qualification remains outstanding.

## Evidence

[The archive](evidence.tar.gz) contains source identity, CI and COPR records, build logs, effective repository configuration, signing verification, guest scripts, history results and login transcripts. [The identity record](identity.json) records accepted checks and artifact hashes; `SHA256SUMS` covers retained files. The tests use the existing [VM runner](../../packaging/vm.py), [login test](../../packaging/test-login.py) and installed history suites. Package signature checking remained enabled throughout.
