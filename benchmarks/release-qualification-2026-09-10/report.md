# Release-mode RPMs reproduce and pass fresh Fedora QEMU login

Two independent canonical builds of commit `13cb60d` produced identical native manifests and RPM bytes, and both complete build/integration suites passed. The agreed RPM then passed installation, real serial-console PAM login, interactive prompt readiness, job control, legacy migration and post-reboot login in a fresh Fedora 44 QEMU/KVM guest with SELinux enforcing. The qualification exposed a serial-test synchronization bug; waiting for complete child acknowledgement lines fixed it without changing the shell.

| Gate | Result |
| --- | --- |
| Independent canonical release-mode builds | Two clean detached worktrees, separate output directories, the pinned Rocky Linux 8.10/glibc 2.28 SDK, GCC 8.5.0; both reference and native upstream Zsh suites and the complete native installation suite pass in each worker |
| Native installation identity | Both manifest SHA-256 values are `8fd195e5f2f90778ace8a3c231c4e6918f9c78a43a5b83d86c0c5107925a43b6` |
| RPM byte agreement | Both 2,579,128-byte RPMs have SHA-256 `4673ac78ed5d8060d7449cc20c92007327c22a702f1a590b4eebdedbd4ee58ed` |
| Fresh system installation and version | DNF installation, native inventory and `rpm -V` pass; the installed manifest matches the build manifest and `--wsh-version` reports `release build` and clean source revision `13cb60dcc0ff28d8d49ca55de30e831f98d3801d` |
| Actual PAM login and prompt readiness | 21 successful serial-getty logins across empty-home, Wsh-prompt, confined SELinux, migrated, resource-failure and post-reboot cases; native OSC 133 readiness is required |
| Native job control | 11 successful Ctrl-Z, `fg`, Ctrl-C and status-130 checks, including six consecutive paired repeats with existing/Wsh prompts and three post-reboot accounts |
| Legacy launcher migration | The actual v0.3.0 launcher remains first in PATH until explicitly renamed; absolute native invocation works with corrupt legacy activation state; account-shell transition, lookup refresh, explicit legacy access and preserved configuration/history/state all pass |
| Missing or unusable optional state/resources | Corrupt, unreadable and incompatible legacy activation state, missing/unreadable/incompatible helper, and missing integration all preserve actual PAM shell access; package files are restored and verified |
| Account configuration and reboot | Authenticated unprivileged `chsh` passes; boot IDs differ; empty-home, Wsh-prompt, confined and migrated accounts all log in after reboot with SELinux enforcing |
| Package removal guard | Ordinary removal refuses while local accounts use Wsh and leaves package verification clean; the independent Bash recovery account remains available |

## Commands and retained identities

Run `WSH_BUNDLE_STATUS=release ./build/test-reproducible-development-bundles.zsh /var/tmp/wsh-release-qualification-13cb60d` from clean commit `13cb60d`. The two manifests retain the upstream source/binary identities, SDK input digest, compiler, target, build flags and fixed source epoch. `identity.json` binds the source scripts, both result archives and their individual files. `build-results.tar.gz` retains both RPMs/manifests, build logs and detailed test outputs. This qualification uses the existing version `0.3.1`; version selection remains separate.

The QEMU guest uses a fresh overlay of Fedora's signature-verified `Fedora-Cloud-Base-Generic-44-1.7.x86_64.qcow2`, SHA-256 `28680fe5b371a5a82ebf43a31926e086a168e59949d03969c5093e7071f90b7f`. `vm-results.tar.gz` retains the image verification, launch command, seed configuration with a public test key, exact guest scripts, test source, transcripts, results, package inventory, installed manifest and boot IDs. It excludes private SSH keys and VM disks. The guest was powered off after testing; the host installation and account shells were not changed.

## Serial test correction and qualification limits

The original job-control test twice timed out after receiving only `CH` or `C` from the resumed child's acknowledgement. Guest process inspection showed that `fg` had put the running child in the foreground. The test sent Ctrl-Z immediately upon receiving the `CHILD_READY` prefix, allowing it to interrupt the child's output before the line was complete. The smallest counterfactual waits for `CHILD_READY\r\n` and `CHILD_RESUMED\r\n` before the next signal. It passed the first trial, all six paired repeats, migrated login and all three post-reboot job-control cases. `packaging/test-login.py` now uses those boundaries. This is a Wsh test-harness correction, with no confirmed upstream Zsh defect.

Two setup observations are retained separately from product results: copying the legacy launcher without preserving mode made its first private migration check fail until the guest copy was made executable, and a package inventory check issued during deliberate helper replacement correctly reported the injected modification. The sequential restored-package checks pass. The original failed serial test also left a session open, so the following login attempt was invalid; the corrected runs start from a reset getty and complete logout.

These are unsigned local qualification artifacts built with release-mode metadata, not an official release. The test fixtures cover the documented migration sequence and real TTY/PAM login; a complete graphical GDM session and the user's full private configuration were not exercised. A version change requires its own exact-candidate CI and release builds. No timing comparison, push, tag or publication is part of this result.
