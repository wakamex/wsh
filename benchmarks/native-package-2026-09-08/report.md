# Native RPM passes Fedora account login and transaction tests

The packaged native executable starts for fresh accounts without Wsh setup or usable activation state. Real serial getty/PAM login passes before and after reboot, including an empty home directory and a confined SELinux account. Package testing found and fixed private file modes inherited from the per-user bundle. The result is a working local RPM prototype; incompatible upstream ABI upgrades and release qualification remain open.

| Tested boundary | Result |
|---|---|
| Stable system account shell | Root-owned `/usr/bin/wsh` points to `/usr/libexec/wsh/bin/wsh`; package owns `/etc/shells` registration |
| Fresh accounts | Actual PAM login passes with Fedora Zsh skeleton files and with no startup files |
| Missing, corrupt, unreadable, incompatible activation state | Login remains usable; native startup does not consult that state |
| Missing, unreadable, incompatible optional runtime | Actual PAM login with Minimal requested still reaches a usable shell |
| Missing optional integration | Actual PAM login reaches native Zsh without Wsh defaults |
| Noninteractive login invocation | `-lc` commands succeed for distinct users and with nonexistent HOME/XDG/state paths |
| SELinux | Enforcing; ordinary unconfined login and `user_u:user_r:user_t:s0` login pass with the default `bin_t` labels |
| User shell selection | Unprivileged `chsh -s /usr/bin/wsh` authenticates through PAM and updates the account |
| Job control through serial login | Child confirms readiness and resume; Ctrl-Z, `fg`, Ctrl-C, and status 130 pass |
| Reboot | Boot ID changes; independent recovery SSH and two Wsh account logins return |
| Real DNF upgrade and downgrade | Both pass; the installed package verifies afterward |
| Running shell across upgrade | Old executable inode remains alive after replacement; previously unused module, autoloaded function, and replacement runtime work under the same Zsh ABI |
| Failed pre-install scriptlet | RPM rejects the update and retains the previous installed package |
| Failed post-install scriptlet | RPM reports failure after installing the new payload; the new shell remains usable |
| Interrupted transaction | Killing RPM and its process group during the paused post-install scriptlet leaves a usable shell; reinstall repairs package bookkeeping and verifies |
| Ordinary removal with local Wsh accounts | RPM refuses removal and the native shell remains usable |
| Removal after account migration | Removal succeeds and clears Wsh registration; independent Bash remains usable |
| Explicit scriptlet bypass | `rpm -e --noscripts` removes the executable despite the guard; independent recovery can reinstall it and restore Wsh login |

## Package fixes and failed checks

The first RPM metadata query found bogus `/usr/local/bin/zsh` and `/bin/zsh` dependencies from executable autoloaded function files. These are sourced data in this installation, so their executable bits are removed.

The first distinct-account login then failed because copying the private bundle preserved a mode-0700 root. Correcting directories alone exposed mode-0700 modules. Strace showed EACCES on the correct installed module path; the final diagnostic named only the later nonexistent build-prefix fallback. The audit retained the native lookup and normalized the entire immutable package payload: readable files, traversable directories, and executable binary entrypoints. Both real-account and module checks then passed. No user configuration repair or SELinux policy module was required.

Two test-harness failures are also retained. A runtime probe put two JSON requests on one line, which the real parser correctly rejected; emitting one line per request fixed the probe. A serial job-control test sent Ctrl-C after a fixed sleep before `fg` had finished resuming its child. The corrected test waits for the child's SIGCONT acknowledgement and then for the native completion marker before checking status.

## Reproduction and qualification scope

The VM uses the [official Fedora Cloud 44 image](https://www.fedoraproject.org/cloud/download/), SHA256 `28680fe5b371a5a82ebf43a31926e086a168e59949d03969c5093e7071f90b7f`. Its checksum file verifies with Fedora 44 signing key `36F612DCF27F7D1A48A835E4DBFCF71C6D9F90A6`. The guest runs Fedora 44, RPM 6.0.1, DNF 5.4.1.0, glibc 2.43, and enforcing SELinux. The retained metadata records complete package versions, labels, commands, RPM requirements/scripts/file lists, and hashes. KVM uses four vCPUs and 4 GiB RAM; there is no package timing claim.

The unchanged native executable and runtime come from accepted bundle `1dec372bc0af0158ff0a2f95587ff01f91fb4c71d3dc1de3d866c7c95a2630dc`; their [upstream, Wsh contract, sanitizer, and timing results](../native-build-2026-09-08/report.md) remain applicable to those bytes. Packaging source and test inputs are retained separately. The RPM deliberately normalizes modes and installs at a new root, which the VM tests exercise. The package retains the existing helper and duplicate private `bin/zsh` pending later migration work.

No full GDM desktop session was started. The graphical-login-related coverage is the noninteractive login-shell invocation boundary, alongside actual PAM/TTY authentication and SELinux. The original account's reported GDM failure cause remains unproven. The interruption test kills the transaction after payload installation; it does not model power loss during individual file writes. Package replacement uses the same Zsh ABI, so it does not qualify loading future incompatible modules into an old running shell. Ordinary removal protects local `/etc/passwd` accounts on the registered paths; remote accounts, arbitrary aliases, and administrator bypass require an explicit supported policy before publication. These are the remaining decisions for this prototype.

The [plan](plan.md) records the original bounds and the permission-premise audit. `results.tar.gz` retains VM commands, transcripts, signature/checksum, package observations, raw failures, and transaction results. `inputs.tar.gz` retains the exact packaging and test implementation. Local RPM artifacts remain under `/var/tmp/wsh-native-rpm/RPMS/x86_64`; [metadata.json](metadata.json) identifies them without claiming reproducible RPM bytes. Stage 10 retains responsibility for independent builds, the existing glibc floor, migration, and any published artifact contract.
