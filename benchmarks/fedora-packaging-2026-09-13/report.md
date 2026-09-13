# Fedora package layout and shell lifecycle qualification

The packaging changes put the shell, private helper and data in Fedora's standard locations, supply the complete license inventory, declare the patched TOML dependency and follow ordinary shell registration and removal behavior. The glibc 2.28 installed suite and Fedora QEMU login, recovery and transaction tests passed. Fedora source builds use the distribution's flags, RPM processing and debug packages.

## Acceptance checks

The baseline package placed the executable and data under `/usr/libexec`, duplicated the shell binary, omitted license details and blocked uninstall based on local account records. Unfiltered rpmlint reported 32 errors and 31 warnings across its source and binary packages. The acceptance criteria were standard paths, explicit source and license provenance, successful offline rebuild and installed tests, a reviewed lint gate with no unexplained errors, and real login and transaction checks under enforcing SELinux.

The first rebuilds exposed test fixtures that still looked for `bin/zsh` or versioned `share/zsh` functions. Those fixtures now use the native installed paths. A host retry of the floor suite could not load the reference Zsh's modules from its container-specific build path; the complete retry passed in the original container. The installed-license test initially used an unsupported RPM query option and was corrected to read RPM's actual file flags.

| Check | Result |
| --- | --- |
| Offline Fedora 44 source rebuild | Passed as an unprivileged builder with networking disabled, standard compiler/linker flags, normal RPM processing and debug packages |
| Reference and native upstream Zsh suites | Each passed 75 scripts with zero failures and two skips |
| Complete installed suites | Passed on the glibc 2.28 build and the post-processed Fedora source build, including completion, editor ownership, profiling, recovery, protocol and Git-output checks |
| RPM installation and metadata | Passed actual file-layout, nine license-file flags, five bundled-dependency declarations, PAM login, shell registration, removal and recovery checks |
| Unfiltered rpmlint | 24 errors and nine warnings across the SRPM and three binary RPMs; raw output is retained |
| Reviewed rpmlint gate | Zero errors and six warnings after the documented narrow exceptions; remaining warnings are five license duplicates and the local development source filename |
| Canonical package assembly | Two assemblies of one verified payload produced identical RPM bytes |

## Login and transaction coverage

The disposable Fedora QEMU guest passed authenticated unprivileged `chsh`, serial getty/PAM login, Ctrl-Z, `fg`, Ctrl-C and login after reboot with SELinux enforcing. Seven optional-resource and obsolete-state cases preserved a usable shell: corrupt, unreadable and incompatible per-user state; missing, unreadable and incompatible helpers; and missing integration data.

Actual RPM/DNF transactions covered upgrade, downgrade, pre-install failure, post-install failure, interruption during the post scriptlet and package repair. A running shell retained its executable and linked modules, loaded installed functions and invoked the replaced helper after a compatible upgrade. Uninstall succeeded with an account still naming Wsh, removed both `/etc/shells` registrations and left the account record unchanged. The independent recovery account restored that account to Bash and verified login.

This tests TTY/PAM login; a graphical GDM session was not exercised. The v0.4.0-to-new-layout boundary requires restarting Wsh sessions, as documented in the [package review](../../packaging/FEDORA-REVIEW.md#upgrade-boundary).

## Evidence

[Identity and commands](identity.json) record tested inputs and artifact hashes. [Raw evidence](evidence.tar.gz) retains build and lint logs, installed-suite results and disposable-VM transcripts. All local RPMs are unsigned development artifacts. The canonical byte comparison repeats package assembly from one payload; it is separate from the release workflow's two independent full builds.

The public-archive check used the published v0.4.0 commit and rejected deliberately altered input. These qualification SRPMs contain development snapshots. Main-push CI checks the new commit's public archive after it becomes available; pull-request validation uses development mode for merge commits.

The [Fedora review](../../packaging/FEDORA-REVIEW.md) explains licensing, bundled-library policy and each lint exception. Fedora inclusion still requires independent package review and maintainer sponsorship.
