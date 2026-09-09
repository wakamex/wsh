# Native floor builds reproduce and pass the installed contracts

Two clean worktrees at `a98029e` produce identical native payload files, manifests, shell/helper binaries, normalized archives, RPM source archives and unsigned RPMs. The native shell imports no glibc symbol newer than 2.25 and its C helper none newer than 2.17. Both execute on the glibc 2.28 builder extension; all nine native component contracts and eight additional profile, protocol, lifecycle and recovery suites pass there. The unchanged canonical legacy floor suite also passes through its complete relocated-bundle and archive checks.

## Build and dependency contract

Each native build starts from its own worktree, Cargo home, Cargo target and Zsh build directory, with the same locked source, compiler/toolchain, fixed `/workspace` paths, locale, timezone, source epoch and SDK image. No compiled cache is shared. Archives use the existing normalized development archiver. RPMs use the tested metadata normalization with epoch 1788931200 and development release 0.6. Exact commands, environments, source inputs, artifact hashes, ELF version requirements and raw test logs are retained in the floor metadata and archives.

The public canonical image remains unchanged. Native testing extends that digest-pinned Rocky image locally with signature-verified Jansson, zlib development and Python 3.9 RPMs, whose exact package bytes are retained. This local SDK image is an experiment, not a published or approved replacement canonical builder. Native and legacy results identify their separate images and artifact contracts. The two native builds share the same host and locked inputs; this proves repeatability, not independent trust domains.

## Retained environment failures

The first SDK image lacked `python3`; source-lock preparation stopped before building. The corrected SDK supplies Python 3.9. During the first second-build attempt, a concurrent canonical container privately relabeled the same worktree under SELinux and caused permission failures in upstream tests. Sequential worktree ownership resolves that test-environment error. The first component container used Python as PID 1 and left an orphan zombie in the foreground fixture; a proper container init passes the unchanged fixture. All failed logs and the layer audit are retained. No shell or helper behavior was changed to pass these reruns.

The resulting floor RPM also passes actual Fedora PAM login, job control, confined SELinux login and all seven missing-state/optional-resource cases. Its DNF downgrade/upgrade, removal guard and post-reboot checks use the same independent recovery account. These remain unsigned development artifacts. Package publication, signing, canonical image replacement and incompatible resource/protocol upgrade policy require explicit decisions.
