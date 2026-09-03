# wsh

`wsh` is a benchmark-driven Zsh distribution. It pairs current Zsh with fast shared services, an open ecosystem of non-executable themes, curated integrations, and built-in profiling.

## Motivation

Zsh is a capable shell, but building a polished interactive environment usually means assembling a framework, themes, plugins, completion files, and terminal integration. Those pieces often own overlapping machinery for Git state, hooks, caching, background work, and prompt repainting. Choosing a visual theme can therefore also choose its performance and correctness behavior.

A benchmark of representative prompt architectures ran each path in fresh interactive terminals against the same 1,000-file Git fixture. The tested paths ranged from one optional-lock-safe background Git scan to 16 synchronous Git calls per transition, with corresponding differences in prompt latency and state correctness. The detailed evidence and scope are recorded in [MOTIVATION.md](MOTIVATION.md).

`wsh` separates presentation from state collection. A theme definition selects trusted prompt components and declares the structured fields it needs without executing shell code. Shared providers own external commands, asynchronous work, cache invalidation, cancellation, freshness, and publication. Fixing a provider can then improve every theme that uses it.

## What wsh aims to provide

- Immutable release bundles that pair one exact Zsh build with its tested wsh runtime, with explicit, signed, reproducible, atomic, and reversible updates
- Fish-like interactive usability while retaining compatibility with shell commands, Zsh scripts, completion functions, and selected plugins
- An open-submission theme directory where every mechanically valid non-executable theme is listed without stylistic maintainer approval
- Curated prompt components and executable integrations without requiring users to assemble a large shell framework
- Trust diagnostics that identify exact runtime and theme digests, signing and reproducibility records, executable plugins and adapters, local overrides, and the update channel
- Shared structured state providers, beginning with Git prompt state
- Fast editable prompts, bounded asynchronous refresh, and composed repainting
- Built-in profiling and tracing for startup, prompts, providers, child processes, repaints, completion, history, and terminal events
- Reproducible benchmarks and correctness fixtures for every performance claim

## First release

The first release is deliberately narrow. It packages one exact Zsh build, the matching `wsh` runtime, one shared Git-state provider, and two non-executable theme definitions with different presentation and field requirements as one immutable release bundle.

The wsh release pipeline builds and tests Zsh from signed upstream source. Users install the resulting prebuilt bundle; the manager does not compile locally, resolve formulas or dependencies, or manage unrelated software.

That milestone must demonstrate that switching themes changes formatting without granting shell authority or duplicating collection work. It must also pass the benchmarked clean, staged, modified, untracked, detached-HEAD, hostile-value, update-integrity, interrupted-update, and rollback scenarios while meeting documented latency, process, repaint, and optional-lock limits.

An installed bundle never updates only Zsh or only the wsh runtime. Any component change produces a new complete bundle and reruns the full compatibility, correctness, performance, provenance, and rollback gates. Several wsh releases may reuse the same Zsh build, but every wsh release identifies exactly one Zsh source and build identity for each supported target.

## Install

The first supported target is x86-64 Linux with glibc 2.28 or newer. Install the exact `v0.1.3` bundle from its immutable GitHub Release:

```sh
curl --proto '=https' --tlsv1.2 -fsSL https://github.com/wakamex/wsh/releases/download/v0.1.3/wsh-v0.1.3-install.sh | sh
```

Then start it with `wsh run`. The installer uses `~/.local/bin`; if that directory is not on `PATH`, run `~/.local/bin/wsh run` or add it to `PATH`.

After installing `v0.1.3` or newer, use `wsh update --check` to check without changing anything, `wsh update` to install GitHub's current immutable release when newer, or `wsh update --to vX.Y.Z` to select an exact newer release. The command downloads the release-specific bootstrap to a private temporary directory and preserves its digest, provenance, complete-bundle, activation, and rollback checks. Existing `v0.1.1` and `v0.1.2` installations need the exact `v0.1.3` curl command above once because those launchers do not implement `wsh update`. `wsh bundle rollback` returns to the previously active bundle without a network request.

## Development slice

The current code implements the phase-one path. It verifies and atomically selects exact bundles, launches the bundled Zsh 5.9.2 and matching session runtime, collects one versioned Git snapshot with one optional-lock-safe Git process, renders the minimal or Wakamex data-only theme, suppresses stale results and unchanged repaints, emits bounded private traces, cleans up on cancellation or shell exit, and rolls back without starting the broken active bundle. Both bundled theme presentations pass the fixed correctness and performance gates at the glibc 2.28 compatibility floor. A release-specific bootstrap downloads exact immutable-release assets, verifies the native tools against embedded digests, and hands the archive and offline GitHub Actions provenance to the separate install helper before extraction or activation. `v0.1.3` is the current official release; the public theme directory is not implemented.

The retained [minimal-renderer optimization result](benchmarks/minimal-tail-2026-09-02/report.md) records the measured decoder cause, unchanged gates, matched raw-Zsh controls, accepted fixed result, longer stress diagnostic, exact identities, and raw data. The preceding [glibc 2.28 failure](benchmarks/phase-one-glibc-2.28-result-2026-09-02.md) remains available as its fixed-gate baseline, and the earlier [glibc 2.35 result](benchmarks/phase-one-result-2026-09-02.md) remains available for its exact build identity.

The retained [resource-gate result](benchmarks/resource-gates-2026-09-02/report.md) adds fixed tracing-overhead and retained-memory thresholds. The clean bundle built and tested on the glibc 2.28 floor passed with 0.190 ms refresh p90 overhead from tracing and 1,961 KiB added retained PSS at p90.

The retained [installed-startup result](benchmarks/exec-launch-2026-09-02/report.md) covers the normal entrypoint through the first editable prompt. A compact activation record and direct `exec` handoff reduced isolated median launcher overhead from the preceding 1.6 ms implementation to 0.65 ms locally and 0.70 ms in the glibc 2.28 build. At the compatibility floor, complete managed startup reached an editable prompt in 7.963 ms at p90, 2.723 ms over raw bundled Zsh; the launcher accounted for 0.527 ms of that p90 difference.

The retained [runtime-startup result](benchmarks/runtime-job-announcement-2026-09-03/report.md) covers the internal coprocess lifecycle. Runtime startup prints no job announcement, keeps the service in a separate process group, restores interactive job control, survives Ctrl-C at the prompt, and passes the existing cold-start gates.

The retained [verified-install result](benchmarks/verified-install-2026-09-02/report.md) checks a real external GitHub Actions provenance record and the local install transaction. Offline provenance verification took 2.229 ms at p90 across 100 warm samples. Keeping that code in `wsh-install` left the normal launcher below its existing 1.0 ms gates, and a network-only launch trace remained empty.

The retained [bootstrap result](benchmarks/bootstrap-install-2026-09-02/report.md) covers first-install acquisition without self-authentication. Its original fixture rejected tool substitution, missing assets, unsafe destinations, and conflicting installed tools before candidate execution. The [`v0.1.2` public update failure](benchmarks/public-update-v0.1.2-failure-2026-09-03.md) showed that rejecting every differing regular tool also rejected legitimate cross-version updates; the corrective gate now requires digest-verified replacement of installer-owned regular tool paths while retaining substitution and unsafe-destination rejection.

The retained [public-install result](benchmarks/public-install-v0.1.1-2026-09-03/report.md) covers the real immutable GitHub Release path through the first editable prompt. Ten fresh installations passed on Fedora 44 and ten passed at the glibc 2.28 Rocky 8.10 floor. The slower Fedora result completed in 1,756.501 ms at p90, including HTTPS acquisition, provenance and payload verification, extraction, activation, and shell startup. The preceding [`v0.1.0` failure](benchmarks/public-install-v0.1.0-failure-2026-09-03.md) remains the regression baseline for relocatable candidate testing.

Build and test the local slice with:

```sh
cargo test --workspace
./tests/bootstrap-install.zsh
./build/build-zsh.zsh
./build/build-development-bundle.zsh
./tests/runtime-pty.zsh
```

The bundle command prints a local bundle path. Verify it with `cargo run -p wsh -- bundle verify <bundle-path>`. `./build/build-glibc-2.28-development-bundle.zsh` builds and exercises the same development slice on the first tested compatibility floor. The default local path always writes `status: development`. The tag-only release path writes `status: release`, but an equivalent local reproduction remains unofficial because it lacks the immutable GitHub Release and workflow attestations.

The glibc 2.28 builder verifies the complete Rocky package lock and the required Rust 1.95.0 toolchain components, fixes locale, timezone, parallelism, and source timestamps, and emits a canonical `.tar.xz` archive after the complete floor test passes. Run `./build/test-reproducible-development-bundles.zsh <new-output-directory>` from a clean commit to build the same revision in two detached worktrees and require byte-identical manifests, archives, launchers, and installers. Official publication is triggered by an annotated version tag only after the exact commit passes `release-eligible / validate`; two fresh release jobs must reproduce the same bytes before the workflow attests and publishes them.

The retained [two-build result](benchmarks/reproducible-build-947d812-2026-09-02/report.md) produced identical manifests and archives from two isolated local builds. This satisfies the local reproducibility experiment; official releases still require the publication, attestation, immutable-release, and updater-verification gates.

The retained [compiler comparison](benchmarks/compiler-comparison-2026-09-02/report.md) found no consistent performance improvement from GCC 16.2 or Clang 23.1 over the locked Rocky GCC 8.5 build when the target recipe was otherwise fixed. GCC 8.5 remains the development bundle default.

## Later capabilities require evidence

Several useful capabilities are being investigated, but they are not release promises:

- Dynamic completion backed by an application's authoritative command model
- Ordered shell lifecycle events for terminal working-directory and command-zone integration
- Stable pane identity with bounded pane-local and private command history
- Terminal compatibility diagnostics with component-level workarounds
- Structured metadata already available from accepted providers
- Foreground-process startup coordination when a terminal-local wrapper cannot preserve job control

Each candidate begins with a reproducible current weakness, the cheapest owner-local counterfactual, and a measurable consumer improvement. A new daemon, database, protocol, or compatibility layer is not accepted merely because it is architecturally attractive. The admission rules and deferred ideas are recorded in [FEATURES.md](FEATURES.md).

## What wsh is not

`wsh` does not replace the Zsh language, parser, job-control engine, or ZLE line editor. It is not a new shell language, an Oh My Zsh fork, a sandbox for arbitrary Zsh configuration, a promise to support every executable plugin, a terminal emulator, a multiplexer, or a generic daemon for every kind of shell state.

Zsh remains the shell engine. Applications remain authoritative for their command models and state. Terminals remain responsible for panes, rendering, scrollback, focus, and input encoding. `wsh` owns only the distribution, shared services, integrations, and measurements that pass its evidence gates.

## Project documents

- [MOTIVATION.md](MOTIVATION.md) explains the benchmark results and product direction.
- [DESIGN.md](DESIGN.md) defines the Git provider, snapshot, renderer, and distribution contracts.
- [SECURITY.md](SECURITY.md) defines non-executable themes, open directory admission, and the signed reproducible update policy.
- [RELEASES.md](RELEASES.md) defines which GitHub artifacts are official and how reproducibility, attestations, activation, and rollback are verified.
- [DEVELOPMENT.md](DEVELOPMENT.md) defines the vertical-slice, testing, benchmarking, and evidence-retention workflow.
- [FEATURES.md](FEATURES.md) defines how later capabilities enter the roadmap.
- [COMPLETION.md](COMPLETION.md) specifies the Wakterm dynamic-completion experiment.
- [FOREGROUND.md](FOREGROUND.md) specifies the foreground-child counterfactual and job-control tests.
- [TERMINAL-INTEGRATION.md](TERMINAL-INTEGRATION.md) covers lifecycle protocols, pane history, metadata, and terminal diagnostics.
- [IMPLEMENTATION.md](IMPLEMENTATION.md) fixes the first target, implementation languages, bundle format, Zsh provenance, theme scope, and milestone gates.

## License

Original `wsh` work is available under the [MIT License](LICENSE). Bundled or adapted third-party components retain their own licenses and notices.
