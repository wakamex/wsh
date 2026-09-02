# wsh development process

`wsh` changes enter through reproducible correctness tests and benchmarks. Development starts with the smallest local runnable bundle, fixes acceptance gates before implementation, changes one causal factor at a time, and retains enough evidence to reproduce every accepted performance or correctness claim.

## The first vertical slice is local and runnable

The first implementation should prove the complete local path before adding remote distribution or ecosystem infrastructure:

1. A manager selects a local development bundle.
2. The manager validates the bundle manifest and installed-file digests.
3. The launcher starts the bundle's exact Zsh binary and matching runtime.
4. The runtime loads one validated non-executable theme definition through trusted prompt components.
5. The initial Git worker publishes one complete versioned snapshot.
6. The prompt becomes editable, performs bounded asynchronous work, and emits a versioned trace.
7. Correctness and performance are measured through the existing PTY and repository fixtures.
8. Manager-side rollback selects the previous bundle even when the active Zsh or runtime cannot start.

This slice uses local artifacts only. Its manifest identifies it as a development bundle. A local build can reproduce another build byte for byte, but it remains unsigned and unofficial. Only immutable, attested assets published through GitHub Releases are releases. Network updates, the public theme directory, broad compatibility adapters, generic completion, pane history, and terminal lifecycle replacement remain outside this slice.

## Every intervention starts with a fixed gate

Before changing an accepted path, record:

1. The exact current implementation and bundle identity.
2. A runnable baseline reproducer.
3. The observed correctness failure or measured cost.
4. The cheapest change in the current owner that could solve it.
5. The metric and threshold that distinguish a passing result from a failed one.
6. The attempt or time limit for the hypothesis.

Implement the smallest counterfactual first. A broader wsh abstraction is justified only when that counterfactual fails or leaves a second measured consumer with the same problem. After two failed interventions at one gate, audit the premise and require a new hypothesis before editing again.

## Correctness gates precede performance comparisons

A faster path is not accepted when it changes advertised semantics, leaves stale state, weakens cleanup, adds unbounded work, bypasses optional-lock suppression, expands executable authority, or makes rollback depend on a working active bundle. Correctness tests cover the normal fixtures plus malformed messages, cancellation, process exit, signals, hostile provider values, prompt and terminal controls, bundle tampering, interrupted activation, and an unstartable active bundle where applicable.

External contracts are tested against their authoritative parser, schema, or no-side-effect implementation. Self-authored fakes can supplement those checks only when they reject inputs that the real implementation would reject.

## Performance thresholds are recorded before implementation

The first runnable bundle must turn the existing benchmark evidence into explicit pass thresholds before optimization begins. The benchmark specification records the raw Zsh control, first-editable latency, settled-state latency, external process count, optional-lock behavior, repaint count, state correctness, theme validation and render cost, disabled tracing overhead, enabled tracing overhead, and retained memory where relevant.

Thresholds use a stated statistic and retained-sample rule rather than the most favorable observation. Cold and warm work are separated when they exercise different mechanisms. A threshold can change only through a documented benchmark-design correction or a new product requirement, not because an implementation missed it.

## Results identify exact builds and workloads

Every recorded run carries the wsh source revision, bundle manifest digest, Zsh source revision, patch set, target, build configuration, toolchain identity, Zsh binary digest, enabled components, fixture identity, workload, trace mode, benchmark command, host identity, and raw result location. Before-and-after comparisons use the same workload and instrumentation mode, while instrumentation overhead is measured separately.

Reports lead with the motivation, short result, and how it was tested. Detailed methods, thresholds, raw samples, exclusions, and limitations follow. Raw evidence remains available so another run can reproduce the summary rather than relying on copied numbers.

## Accepted changes preserve evidence

An accepted intervention retains its reproducer, fixtures, commands, raw measurements, generated summary, and regression test. Generated reports identify their inputs and should be reproducible from retained data. If later evidence invalidates a result or architecture premise, update or replace the old conclusion rather than accumulating mutually inconsistent plans.

## Reproducible development builds use the release-shaped path

`./build/build-glibc-2.28-development-bundle.zsh` is the canonical target build entrypoint. It verifies the locked Rust toolchain tree, rebuilds the builder from its digest-pinned Rocky base image, requires the complete installed RPM set to match `build/rocky-8.10-packages.lock`, fixes locale, timezone, Cargo parallelism, umask, and `SOURCE_DATE_EPOCH`, runs the floor suite, and produces one normalized `.tar.xz` archive. The package lock records NEVRA, architecture, RPM header SHA-256, payload digest algorithm, and payload digest for every installed package. Repository drift causes a build failure. The lock does not preserve package bytes or guarantee their future availability, so an offline package archive or frozen repository remains a release-infrastructure decision.

`build/rust-toolchain.lock` records the exact Rust and Cargo versions and a path-independent digest of every file in the installed toolchain tree selected by `rust-toolchain.toml`. Verification happens before the toolchain is mounted read-only into the builder. Each isolated build uses its own Cargo home and target directory; Cargo dependencies remain fixed by `Cargo.lock` and crate checksums.

`./build/test-reproducible-development-bundles.zsh <new-output-directory> [revision]` requires a clean worktree, creates two detached worktrees at the exact commit, runs the complete builder sequentially without sharing build or compiler caches, and compares both manifests and canonical archives byte for byte. Failed comparisons retain both workers and logs for diagnosis. A passing local comparison establishes repeatability across those two isolated builds, not independent infrastructure or official release status.

The feature admission rules and deferred triggers are defined in [`FEATURES.md`](FEATURES.md). Bundle, theme, and update trust properties are defined in [`SECURITY.md`](SECURITY.md). The runtime and immutable bundle boundaries are defined in [`DESIGN.md`](DESIGN.md).
