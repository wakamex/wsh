# Native reproduction passes and obsolete Rust sources are removed

Two fresh worktrees at ebe2b4c independently pass the complete canonical native build and test pipeline and produce byte-identical manifests and RPMs. The manifest SHA-256 is 50da095f371a1ab0d89c7a0afbae107874a419492c87bb469af171c7a1438510; the RPM SHA-256 is 1aaa916d7b0974f11f09697683080ae2c2891b8f1a9697409fd11fa06b24f129. The reproduced package installs through DNF in the disposable Fedora 44 VM, verifies with RPM and starts an unprivileged login shell.

Actual package transactions pass upgrade, downgrade, failed pre/post scriptlets, interruption after payload installation, repair and use of new resources from a still-running old shell. Earlier serial PAM login, job control and account-shell removal protection are retained in the distribution build report. No host account shell was changed.

## Removed responsibilities

The launcher, installer and runtime Rust crates, Cargo manifests and lock, rustup/toolchain lock, Rust verifier, bootstrap generator, legacy bundle archiver, redirecting startup files and obsolete manager-only test drivers are removed. The selected native source lock remains unchanged. There is no Cargo/rustc invocation in active build, validation or publication tooling. Historical experiments and their original implementation bytes remain available through the immutable source-tree verifier.

The first worktree experiment exposed a packaging lookup of Git metadata outside the container mount. RPM assembly now honors the source timestamp already resolved by the canonical builder. A real RPM records an explicitly supplied timestamp, and both fresh builds pass after this correction. The failed boundary probe and corrected package log are retained.

These are unsigned local development packages. GitHub publication, a release tag and a hosted DNF repository were not exercised or created. Prototype Rust/C comparison scripts may still accept historical reference binaries; they are not dependencies of the native distribution. The editor ownership prototypes are separate work and remain unselected.

## Fresh build after source removal

A fresh worktree at 32d2bc6 also passes the complete canonical native pipeline after the obsolete crates, toolchain files and legacy drivers are physically absent. Its manifest is 9cc80c7e143474d8ba6d690bb2eb3658c7eb2b06fa809e65e6bd83fd60995161. The floor log, manifest and raw checks are retained in post-retirement.tar.gz and verified by the shared entrypoint.
