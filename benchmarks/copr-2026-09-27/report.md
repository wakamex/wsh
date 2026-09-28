# COPR history update qualification

Fedora 44 x86-64 users can upgrade to `wsh-0.4.0-2.fc44` through DNF. This package adds persistent history defaults and native pane-first history with merge-on-exit. The signed package passed upgrade, fresh installation, 65 history checks, real login, job control, reboot and removal in a disposable Fedora VM with SELinux enforcing.

## Results

| Check | Result |
| --- | --- |
| Public source and CI | Clean commit `3f15fec0de1786ca7fe0d0136af1759f5a86ce8f` matched the public archive and remote main. [Run 36359921824](https://github.com/wakamex/wsh/actions/runs/36359921824) passed `release-eligible / validate`, including the glibc 2.28 installed suite and offline Fedora rebuild |
| COPR rebuild | [Build 11043156](https://copr.fedorainfracloud.org/coprs/build/11043156/) succeeded with build networking disabled and full `%check`. Reference and native upstream suites each reported 75 successful scripts, zero failures and two skips; the complete installed Wsh suite passed |
| Signed upgrade | Actual DNF upgrade replaced `0.4.0-1.fc44` with `0.4.0-2.fc44`. Package signatures and digests, source identity, `rpm -V`, installed layout, licenses, bundled declarations and shell registrations passed |
| Installed history | The signed RPM passed 30 persistent-history/session-isolation checks and 35 native pane-history checks as an unprivileged user in real PTYs |
| Login and job control | Real serial getty/PAM login passed before upgrade, after upgrade, after reboot and after fresh installation. Every run checked Ctrl-Z, `fg`, child resumption, Ctrl-C and status 130 |
| Fresh install and shell selection | DNF removal and installation passed; an unprivileged account authenticated through `chsh` and selected `/usr/bin/wsh` |
| Removal and recovery | Removal deleted the executable, helper and shell registrations while preserving the account's shell record. The independent recovery account restored Bash and verified login; the VM was shut down with Wsh removed |
| Wakterm coexistence | Before publication, the qualified development build passed 38 pane-history checks with actual OMZ and Wakterm adapters, plus Wakterm's automatic-injection test for startup order and single ownership of terminal markers and pane history |

## Package identity

| Item | Value |
| --- | --- |
| Package | `wsh-0.4.0-2.fc44.x86_64` |
| Signed RPM SHA-256 | `65ca0b8b2a9a582901c5db6c13c9b8e469d902dbba3b981ee8116dd1d49c705c` |
| Installed Wsh SHA-256 | `c20cdc7386a4c52d39e5c2d65b83d39be4f9ce005c4761df63fccf74ce12ab11` |
| Installed manifest SHA-256 | `a70d54eab2fbcea8b555a8c310126703a08a470330aa8cfc9528a8f28e296439` |
| Signing key fingerprint | `69A9B67B68983B6F064E499E6A3CFDF5066D9E4E` |
| Compiler and target | GCC 16.2.1, Fedora flags and RPM processing, `x86_64-redhat-linux` |
| Zsh source | `cad0d67c76e2be7371cf3526b79ea2581810d35a` with selected Wsh patches |

The product version remains `0.4.0`; RPM release `2` makes this update newer for DNF. No GitHub version tag or canonical GitHub artifact was created. This Fedora rebuild has its own dependencies and identity. Real Wakterm mux-restart qualification remains the next integration check; the login tests cover TTY/PAM rather than GDM.

## Method and retained evidence

The publication gate required exact-commit CI, source-RPM integrity, a successful COPR rebuild with checks enabled, then actual signed DNF transactions and installed tests. The repository retained `gpgcheck=1` and `repo_gpgcheck=0`. Login tests used the existing disposable Fedora fixture and an independent Bash recovery account. Different boot IDs confirmed an actual reboot.

[The evidence archive](evidence.tar.gz) retains CI and COPR records, build logs, source inventory, effective repository configuration, installed manifest, public signing key, exact guest scripts, PTY transcripts, package hashes and check outputs. [The identity record](identity.json) includes accepted gates and the archive hash; `SHA256SUMS` covers retained files. The first guest history-test invocation encountered unreadable test scripts copied with mode `0600`; changing those fixture scripts to `0644` allowed the unprivileged test account to run them. Both attempts are retained. No implementation fix was needed during package qualification.

The [pane-history report](../pane-history-2026-09-26/report.md) records behavior and performance qualification. This publication report adds package-level correctness checks, without claiming new performance measurements.
