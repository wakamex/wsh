# Source RPM rebuild and Fedora login qualification pass

Wsh now has a source RPM that compiles the pinned Zsh sources and native C implementation inside a clean Fedora build environment. The offline, unprivileged rebuild passed both upstream Zsh suites and the shared installed correctness suite, produced the main RPM plus debuginfo and debug-source packages, and passed installation and login tests in a fresh Fedora 44 QEMU guest with SELinux enforcing.

| Gate | Result |
| --- | --- |
| Self-contained source package | The real SRPM contains the spec, Wsh source archive and pinned upstream Zsh archive; source inspection rejects prebuilt Wsh payloads and verifies the recorded source inventory |
| Missing or altered offline inputs | Missing upstream archive, altered upstream bytes and altered Wsh C source are rejected; the actual offline builder rejects a missing archive before compilation |
| Independent source preparation | Two preparations produced byte-identical Wsh source archives; upstream bytes match the pinned digest |
| Clean distro rebuild | Fedora 44, GCC 16.2.1, glibc 2.43 and RPM 6.0.2; declared dependencies installed before an unprivileged rebuild with networking disabled and no repository or host cache mounted |
| Compiler flags and RPM processing | Fedora hardening, LTO and linker flags retained; normal stripping and debug processing retained; installed inventory regenerated after processing |
| Debug packages | Both debuginfo and debug-source RPMs produced; debug-source contents include upstream Zsh and Wsh C sources without missing-source warnings |
| Correctness | Reference and native upstream Zsh suites pass, followed by the shared manifest, build-mode, highlighting, ownership, autosuggestion, recovery, profiling, completion, history, directory and runtime checks |
| Installed RPM | `rpm -V` and the native inventory verifier pass; package registers both `/usr/bin/wsh` and `/bin/wsh`; unprivileged PAM-authenticated `chsh` selects Wsh |
| Native login and job control | Three real serial-getty/PAM logins pass: empty home, Wsh theme and post-reboot; each passes Ctrl-Z, `fg`, Ctrl-C and prompt return |
| Removal | Removal refuses while the account uses Wsh, leaving verification clean; after switching back to Bash, removal succeeds and unregisters both shell paths |

## Reproduction and retained inputs

Run `./packaging/test-source-rpm.zsh NEW_OUTPUT`. It creates the SRPM, prepares a Fedora image from its declared dependencies, records the resolved image and package inventory, then runs source inspection and `rpmbuild --rebuild` with `--network=none`. The same script is a required validation job. `qualify-vm.py` drives the installed tests against an independently prepared disposable guest using the existing VM and real PAM-login harnesses.

`identity.json` binds every file in `results.tar.gz`, including the SRPM, three output RPMs, both Wsh source archives, source and compiler identities, dependency inventory, complete build log, queried RPM contents/dependencies, guest commands, installed manifest, boot IDs, serial transcripts and test source. The source archive preserves the actual tested inputs at `c3c71a02396a777125036d62277ea2488fd89975+dirty`, with a hash for every included file. These are unsigned local development artifacts. The retained-evidence entrypoint verifies this result alongside the existing historical results.

The guest used a fresh overlay of the previously signature-verified Fedora 44 image with SHA-256 `28680fe5b371a5a82ebf43a31926e086a168e59949d03969c5093e7071f90b7f`, rechecked before creating the overlay. An independent Bash recovery account remained available. The guest was powered off after qualification; private SSH keys and VM disks are excluded from retained evidence.

## Packaging corrections and scope

The initial source archive omitted a PTY fixture imported by installed tests. Including that source fixture made the complete installed suite pass. RPM debug collection also exposed the canonical builder's early deletion of temporary Zsh sources. Source builds now retain those sources until RPM finishes, and preserve native compiler/test output in the outer build log before RPM removes its build tree. These are Wsh packaging integration issues, with no confirmed upstream Zsh defect. The first VM harness attempt used the retired `wsh version` command; using the current `wsh --wsh-version` interface corrected the harness without changing the package.

RPM reports its existing duplicate build IDs for the identical `bin/wsh` and `bin/zsh` shell copies, and warns that this initial spec has no changelog entries. The two source archives reproduce; RPM 6's expanded-spec metadata includes source/build directory paths, so source agreement is recorded separately from SRPM wrapper bytes. A Fedora rebuild has its own library requirements and does not inherit the canonical package's glibc 2.28 floor. The canonical GitHub publication path remains separate. This qualification covers x86-64 Fedora and real TTY/PAM login; it does not exercise graphical GDM or establish a runtime performance comparison. No COPR project, publication, push or tag was created.
