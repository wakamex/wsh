# First wsh implementation

The first implementation targets `x86_64-unknown-linux-gnu`, uses Rust for the manager and shared runtime, keeps a thin trusted Zsh adapter for shell-process integration, and ships one complete content-addressed bundle built from the signed upstream Zsh 5.9.2 source release. It does not use a system Zsh or a third-party Zsh binary for an official bundle.

This document fixes the first vertical-slice choices and acceptance gates. It does not make the unsigned local slice an official release.

## The first target is x86_64 Linux with glibc

Development begins on the Fedora host, but the host's glibc version does not become the compatibility floor by accident. The release builder will use a recorded older glibc baseline selected by an install-and-PTY test on the oldest supported environment. The exact minimum distribution or glibc version remains unset until that test exists.

Additional architectures, musl builds, and other operating systems require their own build identities, runtime fixtures, and benchmark results. They do not enter the first vertical slice.

## wsh builds Zsh from signed upstream source

The Zsh project publishes signed source archives rather than an official portable Linux binary distribution. The first bundle therefore builds Zsh 5.9.2 from its upstream signed release archive. The build records the archive URL and digest, verified OpenPGP signing key fingerprint, corresponding source revision, patch set, configure arguments, compiler and linker identities, dependency identities, target, and resulting file digests.

The initial patch set is empty. The release build includes the Zsh executable, required loadable modules, functions, and other runtime files rather than copying `/usr/bin/zsh` from the build host. The portability experiment will determine which non-glibc runtime libraries must be included and which target ABI requirements can safely remain system dependencies. That decision is made from dependency inspection plus execution on the compatibility floor, not from the Fedora development machine alone.

Compilation happens in wsh release infrastructure. The installed manager downloads a completed bundle and never resolves formulas, builds Zsh, substitutes system libraries, or falls back to compiling source on the user's machine. This borrows the managed-runtime installation shape used by tools such as uv and the prebuilt-artifact shape used by package managers, but `wsh` manages only its own complete distribution. It has no general package index, dependency solver, formula language, or authority over unrelated software.

The first accepted bundle uses stable Zsh 5.9.2. The current upstream development revision is a separate benchmark candidate, not a second initial update channel. `wsh` moves to a development revision only when a named capability or measured improvement passes the complete Zsh, integration, correctness, performance, and rollback gates. A later stable Zsh release is also a new full-bundle candidate.

## The manager and runtime are Rust programs

The stable manager and launcher are Rust. The shared runtime and initial Git provider are Rust. One runtime process belongs to each interactive `wsh` session; prompt transitions do not start another runtime process. The Git provider initially performs the demonstrated one-process optional-lock-safe Git scan rather than embedding Git or adopting a persistent Git index.

A small bundled `integration.zsh` adapter owns hooks, ZLE descriptor callbacks, prompt installation, snapshot transfer, and repaint requests because those interfaces exist inside Zsh. It contains no theme-specific Git collection. Its protocol with the runtime is versioned and bounded. A native loadable Zsh module remains deferred until profiling isolates material adapter, serialization, or copying cost.

The Rust workspace should begin with the smallest separation that preserves the installed authority boundary: a manager executable, a runtime executable, shared manifest and protocol types, and integration tests. Additional crates require a concrete ownership or compile-time benefit.

## One repository preserves atomic product and build changes

The first implementation keeps the manager, runtime, Zsh adapter, schemas, themes, build recipe, tests, and benchmarks in one repository. A change can therefore update code, its bundle recipe, compatibility fixtures, benchmark gates, and documentation in one reviewed commit. The initial layout is:

```text
crates/
├── wsh/
└── wsh-runtime/
integration/
schemas/
themes/
build/
tests/
benchmarks/
```

The `build/` directory remains a logical producer boundary. It accepts explicit source, recipe, toolchain, container, and target identities; produces a bundle and machine-readable manifest; does not read undeclared repository or host state; exposes one documented CI entrypoint; and has focused tests. The manifest records the product revision and build-recipe identity even while both come from the same commit.

A separate build repository is deferred until it reduces demonstrated coordination or security cost. Triggers include a second consumer for standalone Zsh artifacts, an independent build release cadence, a platform matrix requiring separate ownership or infrastructure, or build permissions that must be isolated from ordinary development. Until then, a repository split would prevent atomic changes and add cross-repository provenance without changing the artifact trust boundary.

## Bundles are content-addressed complete installations

The first managed installation layout is:

```text
~/.local/bin/wsh
~/.local/share/wsh/
├── bundles/
│   └── <manifest-sha256>/
│       ├── manifest.json
│       ├── bin/
│       │   ├── zsh
│       │   └── wsh-runtime
│       ├── lib/zsh/
│       └── share/wsh/
│           ├── integration.zsh
│           ├── schemas/
│           └── themes/
├── state/
│   ├── active
│   └── previous
└── cache/
```

The manager at `~/.local/bin/wsh` remains outside the selected bundle so it can verify, activate, and roll back a bundle whose Zsh or runtime cannot start. Mutable configuration, local themes, history, traces, and provider caches also remain outside bundle directories.

`manifest.json` is strict machine-generated JSON. Its initial schema records at least:

- Manifest schema version, bundle status, release identity, target, and minimum manager version
- Zsh source archive, digest, verified signing identity, source revision, patch set, configure arguments, and build toolchain
- Rust source revision, lockfile digest, target, compiler, profile, and build inputs
- Runtime protocol, provider schema, theme schema, and integration API versions
- Entrypoints and the path, type, mode, size, and SHA-256 digest of every payload file
- Runtime library and ABI requirements not carried inside the bundle

The SHA-256 digest of the exact manifest bytes is the bundle directory identity. The manifest does not list itself; signed release metadata authenticates its digest, and its file table covers every other file in the bundle. Schema version 1 rejects unknown fields, absolute paths, `..` traversal, special files, and symbolic links. Files are unpacked into a new directory, checked against the manifest, smoke-tested, and only then selected by an atomic replacement of the small `active` state file. A development manifest says it is unsigned and cannot be promoted in place to an official bundle.

## Theme schema 1 covers minimal and Wakamex presentations

Themes use strict versioned TOML parsed as data, with unknown keys rejected. Schema 1 has no expression language or arbitrary conditional code. It can arrange and configure five trusted prompt components:

- `context` for bounded local or SSH user and host presentation
- `cwd` for the current directory
- `git` for the first typed Git field set
- `duration` for completed-command duration
- `prompt-character` for ordinary, failed, and privileged prompt state

The first bundle contains a deliberately minimal theme and a presentation port of the [Wakamex theme](https://github.com/wakamex/wakamex-zsh-theme). The Wakamex port is the useful broad schema test, not a port of its collector or executable theme code. It covers its left prompt, changed cwd and repository context, SSH context, status-sensitive prompt character, main-branch hiding, branch and detached labels, staged, modified, untracked, ahead, behind and diverged markers, repository-operation markers, duration threshold, reset behavior, and safe literal rendering. Each advertised provider field receives a fixture before the port is described as complete.

The runtime owns transient presentation state such as whether a context changed or a duration has already been shown. A theme selects bounded named behavior but cannot match commands, register a clear hook, or execute a reset action.

## The first benchmark gates preserve the demonstrated path

The cross-theme `zsh-theme-bench` A and B latency bands remain comparative report grades. The 15 ms B ceiling is too loose to serve as the first `wsh` release gate, while the 5 ms A ceiling is initially a stretch target because the accepted precursor's worst updated-state sample added 7.284 ms over the raw control.

The first reference workload is the pinned 1,000-file fixture and clean, tracked-dirty, untracked, staged, and detached-HEAD scenarios from [`core-theme-benchmark-2026-09-02.md`](https://github.com/wakamex/zsh-theme-bench/blob/main/research/core-theme-benchmark-2026-09-02.md). That accepted report's raw control uses its pinned Zsh 5.9 and remains the historical cross-theme comparison. Before measuring the wsh provider, the same PTY workload must also produce matched controls from the exact bundled Zsh 5.9.2 binary: raw bundled Zsh without wsh integration, bundled Zsh with the idle integration and runtime, the direct one-scan Git control, and the complete provider and renderer. These outputs distinguish Zsh cost, resident wsh overhead, equivalent collection work, and the complete product path.

| Property | First milestone gate | Accepted precursor reference |
|---|---:|---:|
| First-editable maximum added over raw Zsh | At most 2.0 ms | 1.172 ms |
| Updated Git p90 added over raw Zsh | At most 7.1 ms | 7.005 ms in the highest measured updated state |
| Updated Git maximum added over raw Zsh | At most 8.0 ms | 7.284 ms |
| Git processes per transition | At most 1 | 1 |
| Git processes without `GIT_OPTIONAL_LOCKS=0` | 0 | 0 |
| Repaints for a changed rendered result | At most 1 | 1 |
| Repaints for an unchanged rendered result | 0 | 0 for the measured clean transition |
| New runtime processes per prompt transition | 0 | Not measured as a separate Rust runtime |
| Advertised semantic checks | 100 percent | 20/20 clean, dirty, and untracked; 1/1 staged and detached HEAD |

The settled-latency stretch target is the report's A band of at most 5 ms added over the raw maximum. Missing the stretch target does not weaken the fixed 7.1 ms p90 or 8 ms maximum gates. The p90 gate uses 0.1 ms precision because the accepted reference measured 7.005 ms over raw and the benchmark summary reports latency to 0.1 ms; this threshold was fixed before measuring a wsh provider. The runtime also records retained memory, CPU time, direct-control overhead, protocol bytes, theme validation and render cost, and tracing overhead before a release threshold is assigned to those measurements.

Every comparison identifies the wsh revision and manifest digest, Zsh source and binary identities, Rust and C toolchains, target, build configuration, enabled components, theme definition digest, fixture, command, trace mode, host, raw samples, and exclusions.

## Remaining choices are fixed by the first experiments

The product boundary, first platform, implementation languages, Zsh release, bundle unit, initial provider, theme scope, and latency gates are decided. The following implementation choices remain, and each has a concrete first-slice test rather than requiring another product-direction decision:

- Select the oldest supported glibc environment and bundled-library boundary by inspecting the release binary and running the install, upstream, PTY, and provider suites there.
- Fix the runtime transport and message encoding by comparing the smallest pipe-based protocol with the latency, cancellation, malformed-message, restart, and backpressure requirements.
- Write the exact manifest JSON and theme TOML schemas, including field meanings and resource limits, against hostile and forward-compatibility fixtures.
- Define runtime startup, crash, and Zsh-exit behavior so a failed provider cannot hang the editor or leave a child process behind.
- Retain the direct one-scan Git control and its exact benchmark identity when judging the Rust provider.
- Choose official signing keys, release hosting, metadata expiration, and key-recovery procedure only after the unsigned local bundle passes. These do not block the first vertical slice.
