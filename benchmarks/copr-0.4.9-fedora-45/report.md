# Wsh 0.4.9 on Fedora 45

Wsh 0.4.9 from [COPR](https://copr.fedorainfracloud.org/coprs/wakamex/wsh/) installs and works on Fedora 45 x86-64. The `wakamex/wsh` project gained a `fedora-45-x86_64` chroot, and build 11372135 rebuilt the tagged v0.4.9 source RPM there. A disposable Fedora 45 virtual machine, created by `packaging/qualification-vm.zsh` from the signed Fedora 45 Cloud Base image, then installed the signed package from the repository, passed the installed regression tests, logged in on the serial console and removed it, with SELinux enforcing throughout.

## Results

| Check | Result |
| --- | --- |
| Source | The source RPM is the one built at tag `v0.4.9` (`0d2b2a21b738958de4531df1b9f7386dbf508629`) for the Fedora 44 build 11317906, SHA-256 `f8e75b16b959fb4a8c92d7d1d4c1e8bfe9f232eaf39937d2fd7555d929693431`; no tracked file changed, so the version stays 0.4.9 |
| COPR rebuild | [Build 11372135](https://copr.fedorainfracloud.org/coprs/build/11372135/) passed for `fedora-45-x86_64` with build networking disabled, the project default, and full `%check`. Reference and native upstream suites each passed 75 scripts with zero failures and two skips; the installed suite passed, including the 26 background index refresh checks |
| Qualification VM | `Fedora-Cloud-Base-Generic-45-1.4.x86_64.qcow2`, SHA-256 `50bdc5e70f6a24f540932d15411c1c6ae9fcfa40fb990d876d83c5cc823b2ad0`, matched the release's `CHECKSUM` file, whose signature verified against `RPM-GPG-KEY-fedora-45-primary`. Cloud-init finished with no errors and its user-data passed schema validation |
| Signed DNF install | `dnf install wsh` installed `0.4.9-1.fc45` from the repository; both OpenPGP signatures and digests passed `rpmkeys --checksig`, and `packaging/test-hosted-rpm.py` passed layout, `rpm -V`, licenses, bundled declarations, shell registration, version and source identity |
| Installed catalog | All 31 installed snapshot files match their SHA-256 names, and every one of the 32 references in the generated `catalog.zsh` resolves to one |
| Installed regressions | As root, the interrupt and `WSH_VERSION` tests passed; as an unprivileged user, the re-source test, 33 history checks, 3 mail-notice checks, the four terminal-doctor cases, 40 interactive-default checks, 5 directory-report checks, the type-ahead test and the symlinked-start test passed, all from the v0.4.9 tag |
| Shell selection and login | Authenticated unprivileged `chsh` selected `/usr/bin/wsh`; serial getty/PAM login and job control passed |
| Removal and recovery | Removal deleted executables and shell registrations while preserving the account record; the account was restored to Bash and logged in; the VM was shut down |

## Package identity

| Item | Value |
| --- | --- |
| Signed RPM SHA-256 | `05a734f30c20ceddf5abaf0664a2b0aa7acc10ddcd59823dbed7f8488b375bd3` |
| Installed Wsh SHA-256 | `1d6304dae6628476fdc3c8d16d0d089198460c992ac7217c2cc3ad73c901abfc` |
| Installed runtime SHA-256 | `cffcf7624e0e45f6969e4760b62d7f8fd9c5f807304e8c3a6525274b76430574` |
| Installed manifest SHA-256 | `7c48dcf957a814e8bf0a8d660041c7e92ed4d15cc8e4a18556efbac16ad190d4` |
| Signing key fingerprint | `69A9B67B68983B6F064E499E6A3CFDF5066D9E4E` |

## Evidence and scope

[Evidence](evidence.tar.gz) retains the COPR build record and logs, the source RPM hash, the verified image name, hash and `CHECKSUM` file, the seed's meta-data and user-data with the host private key and password hash removed, the public client and host keys, the exact guest scripts and outputs, the login transcript, the installed manifest and regression outputs, and the tools that ran them; `SHA256SUMS` covers retained files. No upgrade was tested: no earlier version was ever built for Fedora 45, so the next release's qualification on this VM is the first upgrade test. No reboot test was run, since the package scripts and shell registration a reboot exercises are unchanged since the Fedora 44 reboot qualification.
