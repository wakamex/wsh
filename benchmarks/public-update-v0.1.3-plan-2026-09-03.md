# v0.1.3 public update experiment

The experiment asks whether a release-specific bootstrap can replace an older wsh launcher and installer without weakening downloaded-tool verification, unsafe-destination rejection, bundle authentication, atomic activation, or offline rollback. The accepted implementation must pass a local cross-version replacement fixture before release and the real immutable `v0.1.1` to `v0.1.3` path after publication.

## Baseline

The retained [`v0.1.2` failure](public-update-v0.1.2-failure-2026-09-03.md) installs `v0.1.1` successfully and then fails the `v0.1.2` bootstrap with `error: SHA-256 mismatch for wsh`. The old active bundle remains intact.

## Smallest counterfactual

Keep the release-specific bootstrap, exact asset URLs, embedded replacement digests, private downloads, content-addressed bundles, native provenance verification, and activation transaction unchanged. Validate both selected native-tool destinations before mutation, reject symbolic links and non-regular files, stage the verified replacement in the destination filesystem, and atomically replace an older regular tool instead of requiring it to equal the new release.

This treats explicitly selected `WSH_BIN_DIR/wsh` and `WSH_LIBEXEC_DIR/wsh-install` paths as installer-owned regular-file destinations. It adds no updater daemon, registry, package solver, compatibility subsystem, or startup work.

## Fixed correctness gates

1. A bootstrap fixture replaces differing regular launcher and installer files with the exact digest-verified candidate bytes and executes the candidate installer once.
2. Changed downloaded launcher or installer bytes fail before either destination changes or the candidate executes.
3. A symbolic-link or non-regular destination fails before either destination changes.
4. Rerunning the same release remains successful.
5. The exact public `v0.1.3` bootstrap updates an isolated `v0.1.1` installation, selects a `v0.1.3` release bundle, preserves the prior bundle, and permits offline rollback to `v0.1.1`.
6. The publicly installed `v0.1.3` launcher reaches the first editable prompt without an internal job announcement, keeps the runtime in a separate process group, and retains interactive job control.

No performance threshold changes. Native-tool replacement adds no shell-startup work, and the public update is a deliberate one-time install operation.
