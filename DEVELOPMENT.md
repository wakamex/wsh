# wsh development process

`wsh` changes enter through reproducible correctness tests and benchmarks. Development starts with the smallest local runnable bundle, fixes acceptance gates before implementation, changes one causal factor at a time, and retains enough evidence to reproduce every accepted performance or correctness claim.

The selected native transition follows [NATIVE-IMPLEMENTATION-PLAN.md](NATIVE-IMPLEMENTATION-PLAN.md). It authorizes prototypes aimed at reducing code, dependencies, duplicated responsibilities, and compatibility glue, including C replacements for working components. Record those costs and test the resulting simplification alongside correctness and performance. The current build and release contracts below remain applicable until their replacements are implemented and validated.

## Native installation and distribution

The product is a native Zsh executable, thin Zsh integration and one C helper per shell session. System packages own installation and updates. Login does not read a per-user activation record. Prompt rendering and shell lifecycle remain local to each shell. Native autosuggestions use the qualified C controller and a generated Zsh adapter. Wsh-owned main syntax highlighting uses the native C parser and a generated configuration/predicate adapter; the pinned redraw lifecycle and optional highlighters remain in Zsh. Recognized upstream external core/main pairs hand main parsing to the same native adapter, retaining their lifecycle, styles and optional highlighters. Modified or unknown main implementations retain ownership.

## Every intervention starts with a fixed gate

Before changing an accepted path, record:

1. The exact current implementation and bundle identity.
2. A runnable baseline reproducer.
3. The observed correctness failure or measured cost.
4. The cheapest change in the current owner that could solve it.
5. The metric and threshold that distinguish a passing result from a failed one.
6. The attempt or time limit for the hypothesis.

Implement the smallest counterfactual first. A Wsh intervention is justified when it produces a measured correctness or performance improvement for a concrete consumer and remains proportionate to that result. A second consumer strengthens the case for a general abstraction but is not required for a focused product feature. After two failed interventions at one gate, audit the premise and require a new hypothesis before editing again.

## Correctness gates precede performance comparisons

A faster path is not accepted when it changes advertised semantics, leaves stale state, weakens cleanup, adds unbounded work, bypasses optional-lock suppression, expands executable authority, or makes rollback depend on a working active bundle. Correctness tests cover the normal fixtures plus malformed messages, cancellation, process exit, signals, hostile provider values, prompt and terminal controls, bundle tampering, interrupted activation, and an unstartable active bundle where applicable.

External contracts are tested against their authoritative parser, schema, or no-side-effect implementation. Self-authored fakes can supplement those checks only when they reject inputs that the real implementation would reject.

## Performance thresholds are recorded before implementation

The first runnable bundle must turn the existing benchmark evidence into explicit pass thresholds before optimization begins. The benchmark specification records the raw Zsh control, first-editable latency, settled-state latency, external process count, optional-lock behavior, repaint count, state correctness, theme validation and render cost, disabled tracing overhead, enabled tracing overhead, and retained memory where relevant.

The profiling acceptance benchmark observes native OSC 133 `B` after ZLE line-init hooks, rather than matching visible prompt text. `tests/profile-readiness.zsh` inserts a 200 ms line-init delay and requires that delay in every normal and profiled readiness measurement. The profile report separately names its own ZLE callback milestone and runtime `precmd` hook span.

Thresholds use a stated statistic and retained-sample rule rather than the most favorable observation. Cold and warm work are separated when they exercise different mechanisms. A threshold can change only through a documented benchmark-design correction or a new product requirement, not because an implementation missed it.

## Results identify exact builds and workloads

Every recorded run carries the wsh source revision, bundle manifest digest, Zsh source revision, patch set, target, build configuration, toolchain identity, Zsh binary digest, enabled components, fixture identity, workload, trace mode, benchmark command, host identity, and raw result location. Before-and-after comparisons use the same workload and instrumentation mode, while instrumentation overhead is measured separately.

Reports lead with the motivation, short result, and how it was tested. Detailed methods, thresholds, raw samples, exclusions, and limitations follow. Raw evidence remains available so another run can reproduce the summary rather than relying on copied numbers.

## Accepted changes preserve evidence

An accepted intervention retains its reproducer, fixtures, commands, raw measurements, generated summary, and regression test. Generated reports identify their inputs and should be reproducible from retained data. If later evidence invalidates a result or architecture premise, update or replace the old conclusion rather than accumulating mutually inconsistent plans.

Before pushing, run `./benchmarks/verify-retained-evidence.zsh` on the final tree, alongside the relevant correctness tests and `git diff --check`. CI calls this same entrypoint, which runs the resource-gate checker test and every accepted evidence verifier listed there. Add new accepted evidence checks to that script so local and CI coverage stay aligned. This checks retained measurements and source identities; it does not rerun timing experiments or replace the canonical bundle suite.

Changes to prompt ownership exposed historical source-hash mismatches in the plugin-doctor, foreground-startup, and native-terminal evidence that feature-specific verification missed. When measured source changes, preserve the original hash and bind its verifier to a historical commit or retained source snapshot whose bytes match it. Keep current behavior covered by current correctness tests and new evidence. The pre-push gate passes only when the complete retained-evidence suite succeeds.

Every vendored component addition or update also updates [`VENDORED-COMPONENTS.md`](VENDORED-COMPONENTS.md). The review records whether source bytes changed, build-only transformations, selected upstream configuration, Wsh-owned lifecycle and compatibility behavior, upstream-suite results, and the reproducer that still requires each divergence.

## Reproducible native builds

Run `./build/build-native-installation.zsh` for the host loop, then `python3 build/native_manifest.py verify INSTALLATION` and `python3 native/check-installation.py INSTALLATION OUTPUT`. Set `WSH_REFERENCE_ZSH` and `WSH_TEST_ZSH` to the pinned reference Zsh with Wsh terminal patches, and optionally `WSH_TEST_OMZ` to a real Oh My Zsh checkout. The version comes from `VERSION`. After changing native source inputs, refresh the explicit lock with `python3 build/update-native-lock.py`; `--check` verifies it without writing.

`./build/build-glibc-2.28-development-bundle.zsh` builds and tests the native installation and RPM on Rocky Linux 8.10. `build/prepare-native-builder.py` extends the immutable builder image using exact, signed RPM downloads, verifies their SHA-256 digests, installs offline and compares the complete installed package inventory. Its committed input digest identifies the SDK independently of container creation timestamps. There is no Rust compiler, Cargo cache or rustup mount. Python, a C compiler, Jansson and zlib development headers are build requirements.

The canonical script runs upstream Zsh tests, native integration contracts, inventory tampering, profile and recovery checks before RPM assembly. Local output remains an unsigned development artifact. `./build/test-reproducible-development-bundles.zsh NEW_OUTPUT [REVISION]` builds two fresh worktrees with separate build directories and compares native manifests and RPM bytes. It requires a clean source tree and preserves failed workers.

Historical benchmark inputs remain immutable. `benchmarks/verify-historical.py` checks their current bytes and executes their original verifiers against the recorded pre-migration Git tree. This preserves comparisons without retaining obsolete crates in the active build. New accepted evidence verifiers belong in the shared entrypoint.

## CI and release authorization

Validation runs the native floor suite and retained evidence, and its final `validate` job requires both to pass. Main-push `release-eligibility.yml` produces `release-eligible / validate`. The annotated version tag must match `VERSION`, point to the eligible exact main commit and include nonempty committed release notes. Never push a release tag without explicit user authorization.

Publication reruns validation and exact-commit eligibility, builds independently on two GitHub workers, compares the RPM and native manifest, retains both build records, attests the asset set and publishes the immutable Release using the committed notes. Reruns validate existing immutable assets instead of replacing them. Downstream verification downloads the public RPM and exercises installation and login in a disposable Fedora container. Package transaction and account-removal guard qualification also runs in a disposable Fedora VM before accepting distribution changes.

Two GitHub workers share a trust domain. Byte agreement establishes repeatability; independently administered builders are needed for an independent trust claim. No release is created by local builds or workflow edits.

## Prompt ownership checks

`tests/prompt-ownership.zsh BUNDLE` tests shared native configuration, login startup, both prompt owners, profiling, and nested regular Zsh. It also runs `native/test-git-prompt-ownership.py` against the real OMZ collector to check redundant hook removal, preserved customization and failed-theme fallback. Pass a real Oh My Zsh checkout as a second argument to repeat the cases against its loader and verify doctor advice before and after the conditional. `tests/foreground-startup.zsh` also accepts `WSH_THEME=` to exercise foreground return with the preserved renderer.

Historical renderer benchmarks require `WSH_THEME=minimal` when run against current source. The current profile benchmark and real-configuration Python harness set it explicitly; prefix other renderer benchmark invocations with the setting. Recorded experiments bind their original source bytes; accepted-source snapshots preserve inputs when a harness subsequently changes.

`tests/directory-jump.zsh BUNDLE [OMZ_DIRECTORY]` tests the pinned directory-jump implementation, exact-copy native takeover, preserved customization/removal state, optional real OMZ coexistence, and actual ZLE completion. `tests/named-themes.zsh BUNDLE` verifies every bundled name through the launcher and runtime. The retained runtime comparisons cover ports, segment transitions, escaping and rejected definitions.

## Native development installation

`./build/build-native-installation.zsh` builds the selected native entrypoint from `build/zsh-sources/zsh-cad0d67c-native.json` through the existing verified upstream builder and development payload assembler. After an intentional C or source-patch change, refresh that explicit input lock with `python3 build/update-native-lock.py`; `--check` verifies it without writing. Use a fresh `WSH_ZSH_OUTPUT_ROOT` when compiler flags or compiled identity change. Run the printed installation's `bin/wsh` directly. All such artifacts are unsigned development builds.

Native startup uses Zsh-owned user-file loading plus `integration/native-before.zsh` and `integration/native-after.zsh`. `native/test-startup.py`, `native/test-recovery.py` and `native/check-installation.py` cover configuration, recovery and component contracts. The [migration guide](NATIVE-MIGRATION.md) documents system paths, native arguments and package-managed updates.

Native builds also select the [qualified compinit scanner](benchmarks/native-adoption-2026-09-10/completion/report.md). Run `python3 native/test-installed-completion.py NATIVE_INSTALLATION REFERENCE_INSTALLATION OUTPUT correctness` against an installation with the original compinit reference, followed by `measure` for the fixed cold/warm/cache and Tab gates. Keep the lifetime regression in the sanitizer suite whenever callbacks or header storage change.

The [combined component floor qualification](benchmarks/native-directory-final-2026-09-10/floor-report.md) validates selected native completion, history and directory ownership at glibc 2.28 alongside the canonical legacy suite. Exact container commands and the scoped startup fixture are retained there; the SDK lacks bwrap, so its four global-file startup cases retain host coverage. The [installed directory report](benchmarks/native-directory-final-2026-09-10/installed-report.md) records the query, persistence, editor, sanitizer and startup gates.

Native assembly uses VERSION and the schema-2 native installation inventory verified by `build/native_manifest.py`. The build, native contracts and RPM assembly no longer invoke Cargo or rustc; the [build migration result](benchmarks/native-consolidation-2026-09-10/build-report.md) records the guarded build and malformed-payload checks. Distribution tooling uses the same verifier and native manifest.

The [installed autosuggestion qualification](benchmarks/native-autosuggestions-installed-2026-09-10/report.md) selects the complete controller. Run `native/test-installed-autosuggestions.py` for editor parity, cancellation, response bounds and paired editing measurements. Canonical builds include its correctness and lifecycle regressions; real OMZ ownership and rebinding are covered by `native/test-autosuggestions-omz.py`, including recognized v0.7.0, modified copies and custom strategies. The [older-copy qualification](benchmarks/native-autosuggestions-older-2026-09-10/report.md) records the additional recognition boundary and startup comparison.

The [installed highlighting qualification](benchmarks/native-highlighting-installed-2026-09-10/report.md) selects complete native main-parser ownership. Run `python3 native/test-installed-highlighting.py INSTALLATION OUTPUT` for actual styles, composed editor regions and bounded redraw lifetime; canonical builds include it. `native/prepare-highlight-full.py UPSTREAM_CHECKOUT installed FIXTURE` prepares all original corpus cases for `native/test-highlight-parser.py`. The symbolic corpus adapter preserves the upstream observer without adding per-token shell calls to the installed path.
