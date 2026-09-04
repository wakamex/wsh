# First wsh implementation

The first implementation targets `x86_64-unknown-linux-gnu`, uses Rust for the manager and shared runtime, keeps a thin trusted Zsh adapter for shell-process integration, and ships one complete content-addressed bundle built from pinned upstream Zsh source. Official release `v0.1.3` uses the signed Zsh 5.9.2 source release. Current development uses accepted upstream commit `cad0d67c76e2be7371cf3526b79ea2581810d35a`. Wsh does not use a system Zsh or a third-party Zsh binary for an official bundle.

This document fixes the first vertical-slice choices and acceptance gates. It does not make the unsigned local slice an official release.

## The first target is x86_64 Linux with glibc

The first tested compatibility floor is glibc 2.28 on Rocky Linux 8.10. The floor test builds the complete development bundle in a pinned Rocky Linux 8.10 base image, rejects any glibc symbol newer than 2.28, and exercises the upstream Zsh suite, runtime and manager suites, relocated-bundle verification, a real provider request, dependency-manifest comparison, and interactive PTY repaint, crash, and cleanup behavior. The exact artifact fails to load on glibc 2.27 because of its `GLIBC_2.28` import. The exact result and system-library boundary are retained in [`benchmarks/portability-glibc-2.28-2026-09-02.md`](benchmarks/portability-glibc-2.28-2026-09-02.md).

Rust documents support for `x86_64-unknown-linux-gnu` on older glibc releases, while the `wsh` floor covers the complete Zsh bundle and its system-supplied libraries. The manifest records glibc 2.28 as the tested floor and separately records every required dynamic-library soname. A lower floor requires the same complete build and execution experiment.

Additional architectures, musl builds, and other operating systems require their own build identities, runtime fixtures, and benchmark results. They do not enter the first vertical slice.

## wsh builds Zsh from pinned upstream source

The Zsh project publishes signed source archives rather than an official portable Linux binary distribution. Stable Wsh bundles build Zsh from an upstream signed release archive and record the archive URL and digest, verified OpenPGP signing key fingerprint, corresponding source revision, patch set, configure arguments, compiler and linker identities, dependency identities, target, and resulting file digests.

An accepted development revision uses a committed source lock containing the canonical `zsh-users/zsh` repository URL, exact commit and tree identities, and the SHA-256 digest of the complete source snapshot. A pushed commit containing the pin authorizes source selection. The ordinary Wsh release tag authorizes publication, and build provenance binds the selected input to the published bundle. Build jobs reject moving refs and changed source bytes. This policy identifies the canonical upstream bytes selected by Wsh without describing an unsigned development commit as maintainer-signed.

The current development revision applies one digest-pinned compiled-source patch and one separate test-only correction. The source patch corrects an offset error that corrupted native OSC 133 prompt identifiers and emits OSC 7 from the native prompt path even when terminal querying is disabled, including after a foreground child changed the terminal's reported directory. The test-only correction fixes five upstream fixtures that attempted to suppress interactive prompts with command-prefix `PS1=` assignments; it changes only files under `Test/` and retains every test. Source and test patches are validated separately, source patches are recorded in the bundle manifest, and an installed Zsh build carries the complete source-lock digest so stale or substituted build output cannot be packaged under newer provenance. The release build includes the Zsh executable, required loadable modules, functions, and other runtime files rather than copying `/usr/bin/zsh` from the build host. The current development bundle carries the Zsh runtime tree and records every system-supplied dynamic library found across the manager, runtime, Zsh executable, and loadable modules.

The glibc 2.28 builder starts from a digest-pinned Rocky Linux 8.10 base image and accepts the installed RPM set only when every package matches the committed NEVRA, architecture, RPM header SHA-256, payload digest algorithm, and payload digest. It verifies every file declared by the locked Cargo, rustc, and target-standard-library component manifests before mounting the toolchain read-only, uses `Cargo.lock`, gives each isolated build separate Cargo and target directories, resolves the exact source identity before entering the container, and fixes locale, timezone, umask, Rust and Zsh parallelism, and `SOURCE_DATE_EPOCH`. Optional developer components do not alter this build identity. The manifest records these identities and effective settings. The RPM lock detects repository drift but does not retain package bytes; an unavailable locked package causes a build failure.

The canonical archive contains the content-addressed bundle directory. GNU tar sorts entries and normalizes timestamps, ownership, and modes, then single-threaded xz applies fixed compression parameters. The archive is extracted and verified before it is accepted. The two-build test starts from one clean commit in two detached worktrees without shared build or compiler caches and rejects any manifest or archive byte difference.

The first local two-build experiment produced identical manifests and archives with archive SHA-256 `5b679a0d99867ee38af7acd8bdd3c9cfe75a3612d555aeaeb5c9f3282811c447`. Its exact inputs, logs, manifest, failed precursor, and scope are retained in [`benchmarks/reproducible-build-947d812-2026-09-02/report.md`](benchmarks/reproducible-build-947d812-2026-09-02/report.md).

Compilation happens in wsh release infrastructure. The installed manager downloads a completed bundle and never resolves formulas, builds Zsh, substitutes system libraries, or falls back to compiling source on the user's machine. This borrows the managed-runtime installation shape used by tools such as uv and the prebuilt-artifact shape used by package managers, but `wsh` manages only its own complete distribution. It has no general package index, dependency solver, formula language, or authority over unrelated software.

Official release `v0.1.3` uses stable Zsh 5.9.2. Current development uses upstream commit `cad0d67c76e2be7371cf3526b79ea2581810d35a`, which is 1,074 commits on `master` after the Zsh 5.9 release. Zsh 5.9.2 was developed on a maintenance branch, so it remains a comparison baseline rather than the start of a linear `master` commit count. The pinned revision passed the upstream suite after the test-only fixture correction and passed the complete Wsh compatibility, correctness, resource, and performance gates at the glibc 2.28 floor. The accepted result and retained evidence are in [`benchmarks/edge-zsh-2026-09-03/report.md`](benchmarks/edge-zsh-2026-09-03/report.md). A later Zsh revision is a new full-bundle candidate.

## The manager and runtime are Rust programs

The stable manager and launcher are Rust. The release installer, shared runtime, and initial Git provider are also Rust. Normal startup reads one compact activation record, validates the recorded type, mode, and size of the four required entrypoints, and replaces the launcher process with the selected Zsh through `exec`. No manager process remains resident. The separate `wsh-install` executable owns archive and attestation work so its larger cryptographic and decompression dependency graph is never loaded during shell startup. One runtime process belongs to each interactive `wsh` session; prompt transitions do not start another runtime process. The Git provider initially performs the demonstrated one-process optional-lock-safe Git scan rather than embedding Git or adopting a persistent Git index.

A small bundled `integration.zsh` adapter owns provider hooks, ZLE descriptor callbacks, prompt installation, snapshot transfer, and repaint requests because those interfaces exist inside Zsh. It contains no theme-specific Git collection and does not reproduce the standard terminal lifecycle. Native Zsh owns OSC 7 and OSC 133 reporting. Its protocol with the runtime is versioned and bounded. A native loadable Zsh module remains deferred until profiling isolates material adapter, serialization, or copying cost.

The launcher records the incoming user `ZDOTDIR`, or `HOME` when it is unset, before selecting the bundle's startup directory. Bundle adapters load applicable user `.zshenv`, `.zprofile`, `.zshrc`, and `.zlogin` files once in native order, honor a user change to `ZDOTDIR`, leave `.zlogout` to the restored user directory, and install interactive `wsh` integration after `.zshrc`. The adapters do not parse, copy, convert, or rewrite startup source. They force only the internal `RCS` transitions needed to reach the matching bundle adapter, skip later user files when the user's own option state requires it, then restore that state. Bundled module and function paths are reasserted before trusted integration while preserving unrelated user paths. For the accepted post-5.9 revision, the managed `.zshenv` disables ZLE terminal queries before `.zshrc` when no explicit terminal policy exists; `WSH_ENABLE_ZLE_TERMINAL_QUERY=1` or a user-defined `.term.extensions` value in the environment or `.zshenv` remains authoritative. This avoids the revision's 500 ms wait on PTYs that do not answer while preserving explicit user policy. The patched native prompt path still emits OSC 7 and OSC 133 without the query, and `.term.extensions` can disable those components independently.

`wsh -- <command> [arguments...]` is the concise exact-startup form, while `wsh run-foreground [--state-root <directory>] [--login] -- <command> [arguments...]` retains explicit bundle and login controls. The manager passes the vector as positional parameters through Zsh's `-s` input mode. Bundle `.zshenv` captures it before user startup, and a one-shot first `precmd` callback removes its state and executes the array directly before other prompt hooks. That callback follows `.term.extensions` and emits OSC 133 `C` and `D` around this first application; native Zsh owns every later prompt and command boundary. The same Zsh owns the foreground process group, stopped-job table, and later prompt. The accepted [foreground-startup result](benchmarks/foreground-startup-2026-09-03/report.md) verifies non-UTF-8 Unix argv, process groups, default and consumed Ctrl-C, Ctrl-Z and `fg`, nested children, reaping, terminal state, startup files, aliases, user hooks, repeated launches, process count, and latency. The [native terminal-integration result](benchmarks/native-terminal-integration-2026-09-04/report.md) adds the first-job lifecycle and disable controls. The dormant adapter added no measured ordinary-startup regression.

The retained [configuration coexistence result](benchmarks/zsh-config-coexistence-2026-09-03/report.md) verifies plain, login, changed-`ZDOTDIR`, disabled-`RCS`, Oh My Zsh, representative theme, and combined ZLE-plugin cases. Plain managed startup added 0.865 ms at p90 over direct integration. Robbyrussell and Wakamex retained material duplicate Git work after `wsh` took presentation ownership, so this adapter does not attempt generic post-source theme unloading or hook removal.

The first accepted editing default vendors `zsh-users/zsh-history-substring-search` commit `14c8d2e0ffaee98f2df9850b19944f32546fdea5` byte for byte and compiles it with the bundled Zsh. The adapter runs after `.zshrc`. It takes runtime ownership from exact pinned upstream and Oh My Zsh copies after a bounded `sysread` comparison, removes their temporary highlight hooks, and reloads the bundled definition. Unknown or modified definitions remain active, custom bindings remain untouched, and `WSH_DISABLE_HISTORY_SUBSTRING_SEARCH=1` disables the default. The retained [correctness and startup result](benchmarks/history-substring-search-2026-09-03/report.md) records the fixed gates and rejected slower paths.

The second accepted editing default vendors `zsh-users/zsh-autosuggestions` commit `85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5` byte for byte and compiles it with the bundled Zsh. It uses upstream's documented manual-rebind mode so the first prompt wraps existing widgets once instead of rescanning them on every prompt. Exact pending copies are recognized through the same bounded in-process comparison and replaced; active, modified, or unknown copies remain external. `WSH_AUTOSUGGEST_REBIND_MODE=automatic` restores upstream scanning, `WSH_AUTOSUGGEST_ASYNC=0` selects synchronous fetching, and `WSH_DISABLE_AUTOSUGGESTIONS=1` disables the default. The retained [correctness, startup, prompt, editing, and process result](benchmarks/autosuggestions-2026-09-03/report.md) records the fixed gates and explicit later-widget rebind behavior.

The third accepted editing default vendors the runtime files from `zsh-users/zsh-syntax-highlighting` commit `2fc57d63067c18b1100ecdbf684fa5baf49459d1` byte for byte and compiles them with the bundled Zsh. Direct source loading through the nested user-startup path ran before ZLE was active and silently installed no redraw hooks, so the clean Wsh path defers source loading until the first `precmd`. An exact core and active shipped highlighter set is recognized through bounded in-process comparisons; Wsh preserves installed hooks or activates missing upstream hooks without sourcing a second copy. Modified active files, custom active highlighters, incomplete installations, and unknown implementations remain external. `WSH_DISABLE_SYNTAX_HIGHLIGHTING=1` disables the default, while upstream highlighter and style configuration remains available. The retained [upstream-suite, correctness, startup, redraw, composition, and process result](benchmarks/syntax-highlighting-2026-09-03/report.md) records the accepted gates and the exact-copy compatibility cost.

`wsh doctor` runs one opt-in diagnostic shell through the same managed startup path and reports the ownership decisions already made by these adapters. It recommends removing only declarations whose loaded source matched a pinned copy exactly, reports modified or unrecognized implementations as preserved, and makes no configuration change. The report travels through a private bounded temporary file, malformed state fails closed, and the child is terminated after 10 seconds. The ordinary launcher does not create a report or start a diagnostic process. The retained [doctor result](benchmarks/plugin-doctor-2026-09-03/report.md) covers exact, modified, disabled, older-bundle, coexistence, and startup gates.

The Rust workspace uses three executable boundaries: the compact manager and launcher, the release installer, and the per-session runtime. The installer split preserves the measured startup boundary while allowing strict archive and GitHub provenance verification. A generated release-specific POSIX shell bootstrap performs acquisition through the host HTTPS client, verifies embedded native-tool digests, and invokes the installer; it is distribution glue rather than another resident component. The explicit update commands resolve a canonical release and reuse that bootstrap without adding another native binary or installation protocol. Additional crates require a concrete ownership or compile-time benefit.

## One repository preserves atomic product and build changes

The first implementation keeps the manager, runtime, Zsh adapter, schemas, themes, build recipe, tests, and benchmarks in one repository. A change can therefore update code, its bundle recipe, compatibility fixtures, benchmark gates, and documentation in one reviewed commit. The initial layout is:

```text
crates/
├── wsh/
├── wsh-install/
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
~/.local/libexec/wsh-install
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
├── bundle-state.json
└── cache/
```

The manager at `~/.local/bin/wsh` and install helper at `~/.local/libexec/wsh-install` remain outside the selected bundle so verification, installation, activation, and rollback do not depend on the active Zsh or runtime starting. Mutable configuration, local themes, history, traces, and provider caches also remain outside bundle directories.

`manifest.json` is strict machine-generated JSON. Its initial schema records at least:

- Manifest schema version, bundle status, release identity, target, and minimum manager version
- Zsh source mode, canonical location, archive digest, source revision and tree, verified signing identity when present, patch set, configure arguments, and build toolchain
- Rust source revision, lockfile digest, target, compiler, profile, and build inputs
- Runtime protocol, provider schema, theme schema, and integration API versions
- Entrypoints and the path, type, mode, size, and SHA-256 digest of every payload file
- Runtime library and ABI requirements not carried inside the bundle

The SHA-256 digest of the exact manifest bytes is the bundle directory identity. The manifest does not list itself; authenticated build provenance binds the archive digest to the exact repository, release ref, source commit, and signer workflow, while the manifest file table covers every payload file. Schema version 1 rejects unknown fields, absolute paths, `..` traversal, special files, and symbolic links. The installer also rejects unsafe or duplicate archive paths, links, special entries, unsupported modes, multiple roots, and resource-limit violations before the manifest is trusted. Files are unpacked into a private new directory, checked against the manifest, smoke-tested, and only then selected by atomically replacing one state record containing the active and previous references. The normal local builder writes `status: development`. The release builder writes `status: release` only for a matching annotated version tag and exact clean revision, but the status is structural metadata rather than proof of authenticity.

Activation state schema 2 stores the verified bundle root, manifest digest, and path, mode, and size for the shell, runtime, integration adapter, and default theme, plus the fixed ZDOTDIR path. Activation and rollback still verify the complete manifest and every payload digest. Ordinary launch trusts that completed activation and the release bundle's immutability, reads only the bounded state record, rejects missing, symbolic, wrong-sized, or wrong-mode launch files, and performs no network or update work. It does not detect a same-size post-activation content mutation; `wsh bundle verify` and `wsh bundle current` retain complete verification for that check. Unsupported state versions fail closed. Because schema 1 was never released, development users remove its state record and activate again rather than carrying a compatibility parser.

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
| Traced runtime-ready p90 overhead | At most 3.0 ms | Not measured separately |
| Traced refresh p90 overhead | At most 0.5 ms | Not measured separately |
| Added retained PSS p90 per session | At most 4,096 KiB | Not measured separately |
| Added retained PSS maximum per session | At most 5,120 KiB | Not measured separately |
| Advertised semantic checks | 100 percent | 20/20 clean, dirty, and untracked; 1/1 staged and detached HEAD |

The settled-latency stretch target is the report's A band of at most 5 ms added over the raw maximum. Missing the stretch target does not weaken the fixed 7.1 ms p90 or 8 ms maximum gates. The p90 gate uses 0.1 ms precision because the accepted reference measured 7.005 ms over raw and the benchmark summary reports latency to 0.1 ms; this threshold was fixed before measuring a wsh provider. The benchmark suite also records CPU time, direct-control overhead, protocol bytes, theme validation, and render cost before a release threshold is assigned to those measurements.

The glibc 2.35 development result passed the fixed gates with a 6.893 ms worst added p90, 7.241 ms worst added maximum, 0.943 ms worst added first-editable maximum, one optional-lock-safe Git process, one changed-result repaint, and all 62 applicable semantic checks. Its preceding failed polling baseline is retained in [`benchmarks/phase-one-result-2026-09-02.md`](benchmarks/phase-one-result-2026-09-02.md).

The first clean glibc 2.28 rebuild passed all fixed Wakamex gates and all correctness gates for both renderers, but the minimal renderer missed its untracked p90 and maximum gates by 0.070 ms and 0.098 ms. Profiling isolated byte-at-a-time prompt decoding in the Zsh integration. A one-pass decoder reduced median decode cost from 279.555 to 93.266 microseconds per field, and the next accepted 20-iteration run passed the unchanged gates with a 6.711 ms worst added p90 and 6.911 ms worst added maximum. The [fixed result](benchmarks/minimal-tail-2026-09-02/report.md) retains the counterfactual, exact identities, raw samples, and a 100-iteration stress diagnostic; the [original miss](benchmarks/phase-one-glibc-2.28-result-2026-09-02.md) remains its failed baseline.

The first [resource-gate result](benchmarks/resource-gates-2026-09-02/report.md) passed the fixed tracing and retained-memory thresholds. Tracing added 1.533 ms at runtime-ready p90 and 0.190 ms at refresh p90. The bundled Zsh and runtime added 1,961 KiB of retained PSS at p90 and 1,981 KiB at maximum over paired raw bundled Zsh; that experiment did not launch through the manager.

The first [manager-launch result](benchmarks/manager-launch-2026-09-02/report.md) found that the normal entrypoint added 38.1 ms at the median by verifying the complete bundle twice. Reusing the activation-time verification record reduced that to 1.6 ms. The subsequent [installed-startup result](benchmarks/exec-launch-2026-09-02/report.md) replaced manifest parsing and child-process supervision with compact state and `exec`: isolated median launcher overhead fell to 0.65 ms locally and 0.70 ms in the glibc 2.28 build. At the floor, normal wsh startup reached its first editable prompt in 7.963 ms at p90, 2.723 ms over raw bundled Zsh, with a 0.527 ms launcher contribution over the direct complete path. This cold-start measurement is separate from the existing first-editable release gate, which measures the prompt returned after a command while asynchronous refresh continues.

Bare `wsh` maps an empty argument list to the existing `run` dispatch and remains an `exec` launcher rather than a supervising process. The [bare-launch result](benchmarks/bare-launch-2026-09-03/report.md) verified process replacement for bare and explicit forms on the glibc 2.28 floor. Bare managed startup reached the first editable prompt in 7.990 ms at p90, adding 0.545 ms over direct complete integration and passing the unchanged startup gates.

The first [verified-install result](benchmarks/verified-install-2026-09-02/report.md) kept the cryptographic verifier out of the launcher and tested it against real external GitHub Actions provenance. Complete warm offline verification took 2.229 ms at p90, while the rebuilt glibc 2.28 launcher remained below the unchanged startup gates at 0.80 ms paired median and 0.702 ms p90 contribution through the first prompt. Invalid provenance and unsafe archives created no install state; failed candidates left the active bundle unchanged; implicit downgrades were rejected; and rollback required no attestation or network access.

The first [release-bootstrap result](benchmarks/bootstrap-install-2026-09-02/report.md) generated a release-specific script containing exact URLs, identities, and native-tool digests. It rejected changed downloads, missing assets, unsafe destinations, conflicting installations, and unsupported platforms before candidate execution or activation. Thirty warm local-file runs completed through the strict installer handoff in 61.642 ms at p90. The later [`v0.1.2` public update failure](benchmarks/public-update-v0.1.2-failure-2026-09-03.md) established that requiring existing tool bytes to equal the candidate also blocked every legitimate cross-version replacement. The corrective gate permits atomically replacing installer-owned regular tool paths only after the downloaded candidate bytes pass their embedded digests, while symbolic links and non-regular destinations still fail before mutation.

The first real public path found that immutable `v0.1.0` failed before activation because its installer smoke test disabled the bundle's relocatable `.zshenv`. The `v0.1.1` correction uses the normal launch environment and adds direct relocated-module coverage. Its [public-install result](benchmarks/public-install-v0.1.1-2026-09-03/report.md) passed 10 fresh installations on Fedora 44 and 10 at the glibc 2.28 floor. Complete HTTPS download through the first editable prompt took 1,756.501 ms at p90 on Fedora and 1,115.246 ms at the floor, below the fixed 5-second gate. Post-install first-prompt p90 was 9.130 ms and 8.446 ms respectively.

Runtime coprocess creation locally disables Zsh job monitoring within the startup function's option scope, and the runtime establishes its own process group before reporting ready. This prevents an internal `[N] PID` announcement before the first prompt while returning the interactive shell with `MONITOR=on` and keeping terminal-generated signals away from the service. The [PTY result](benchmarks/runtime-job-announcement-2026-09-03/report.md) passed process-group and Ctrl-C checks, readiness, asynchronous Git rendering, crash and exit cleanup, and the existing cold-start gates.

The controlled [GCC 16.2 and Clang 23.1 comparison](benchmarks/compiler-comparison-2026-09-02/report.md) kept the glibc 2.28 target recipe fixed and reversed compiler order. Neither modern compiler improved raw Zsh or repeated startup consistently across both blocks, so the locked Rocky GCC 8.5 compiler remains the default. A new compiler comparison requires a measured hypothesis beyond version recency.

Every comparison identifies the wsh revision and manifest digest, Zsh source and binary identities, Rust and C toolchains, target, build configuration, enabled components, theme definition digest, fixture, command, trace mode, host, raw samples, and exclusions.

## The local slice has fixed contracts

The local slice uses inherited pipes and bounded newline-delimited JSON, one process-backed Git scan, strict manifest and theme schemas, an immediately editable fallback prompt, stale-generation rejection, cancellation and process-group cleanup, repaint-on-change, manager-side atomic activation and rollback, and the matched raw, idle-runtime, direct-Git, complete-runtime, and trace benchmark controls. The minimal and Wakamex presentations exercise the same provider through separate data-only definitions.

The initial release scope fixes the target, product boundary, implementation languages, Zsh release, bundle unit, provider scope, theme scope, glibc floor, update authority, and latency gates. An official release requires pinned build inputs, two isolated byte-identical builds, GitHub build attestations, an immutable GitHub Release, updater-side attestation verification, and the complete release gates in [`RELEASES.md`](RELEASES.md). A locally reproduced release-mode archive remains an unofficial copy even when its bytes match the official asset.
