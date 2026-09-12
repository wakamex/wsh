# Wsh architecture

Wsh is a pinned Zsh distribution with native C additions, thin Zsh integration and one optional C prompt helper per shell. Zsh owns the language, startup-file evaluation, job control and ZLE. System packages own installation and updates. This document describes the current source; earlier designs remain in Git history.

## Native entrypoint and system installation

The executable handles explicit Wsh tool options in the first argument position and delegates ordinary arguments to Zsh. Script names, `-c`, login flags and `--` retain their Zsh meanings. The [command reference](NATIVE-INSTALLATION.md#commands) documents diagnostics, profiling, version reporting and foreground invocation.

Native startup resolves resources and applies Wsh integration around Zsh's own user-file loading. It does not reconstruct startup semantics by manually sourcing configuration. The RPM installs the account shell at `/usr/bin/wsh`, resources under `/usr/libexec/wsh`, and registers the supported paths in `/etc/shells`. Bundled modules are linked into the executable; external module loading retains Zsh's ABI requirements.

The original login failure demonstrated that mandatory per-user activation state could prevent account access. An installation-owned default bundle was a viable smaller launcher counterfactual; the [native entrypoint experiment](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-entrypoint-2026-09-08/report.md) supported removing duplicated argument and startup handling altogether. [Native startup qualification](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-build-2026-09-08/report.md) and [Fedora login qualification](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/release-qualification-2026-09-10/report.md) establish the selected path. Missing optional helper resources do not become a prerequisite for basic shell access.

## Editing and compatibility ownership

| Component | Selected responsibility | Evidence |
| --- | --- | --- |
| Completion | C registration scanner inside compinit; Zsh retains initialization policy, auditing and candidate handling | [Installed completion](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-adoption-2026-09-10/completion/report.md) |
| History substring search | Native history navigation with existing ZLE and configuration contracts | [Installed history](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-adoption-2026-09-10/history/report.md) |
| Directory jumping | C data/query and persistence owner, with pinned Zsh editor and lifecycle adapters | [Installed directory qualification](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-directory-final-2026-09-10/installed-report.md) |
| Autosuggestions | Complete C controller with generated Zsh configuration and widget adapter | [Installed autosuggestions](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-autosuggestions-installed-2026-09-10/report.md) |
| Main syntax highlighting | Complete C main parser with generated configuration/predicate adapter; upstream Zsh redraw lifecycle and optional highlighters remain | [Installed highlighting](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-highlighting-installed-2026-09-10/report.md) |

A native replacement is selected from behavior, maintenance cost and measurements, rather than implementation language alone. Existing upstream implementations remain behavioral references and support external-plugin compatibility. [Performance results](PERFORMANCE.md) link the comparisons, including unsuccessful and intermediate approaches through their qualification reports.

Recognition checks the shared upstream catalog first and bounded local Git provenance on a miss. Supported unmodified upstream implementations prefer Wsh ownership, even when a newer upstream release has features Wsh has not incorporated yet. Modified or unverified implementations retain ownership. Component-specific tests preserve settings, custom widgets and unrelated hooks. [Catalog qualification](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/plugin-catalog-2026-09-10/report.md), [Git provenance qualification](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/git-provenance-2026-09-10/report.md) and [component compatibility](VENDORED-COMPONENTS.md) define this boundary. Daily upstream monitoring detects changes for review.

Wsh does not initialize compinit automatically. The user's configuration or framework owns that choice. Automatic and deferred initialization remain unselected because their tested startup or first-use costs exceeded the gates; the adopted scanner is a separate improvement. [Completion](COMPLETION.md) distinguishes those outcomes.

## Prompt ownership and collection

An unset or empty `WSH_THEME` preserves the existing prompt and does not start Wsh's prompt helper. A bundled name or definition path selects Wsh's prompt, right prompt, Git collection and repainting. The choice remains local to the Wsh session. Shared OMZ configuration should skip its executable theme when Wsh owns the prompt; doctor diagnoses overlap without rewriting configuration. [Theme setup](THEMES.md#session-selection-and-shared-configuration) gives the exact conditional.

The per-session helper collects Git state and renders validated theme data. The Zsh adapter owns shell hooks, ZLE callbacks, prompt installation and repaint application. One optional-lock-safe Git process per prompt transition supplies a complete snapshot. Cancellation, generation checks and process cleanup prevent superseded work from replacing newer state; repainting depends on a changed rendered result.

```text
Zsh prompt transition
  -> per-session C helper
  -> Git collection and complete snapshot
  -> C renderer using the selected theme
  -> Zsh adapter applies the prompt and any changed repaint
```

The [runtime protocol](schemas/runtime-protocol-v1.md) records requests, snapshots and publication semantics. [C collector qualification](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-git-2026-09-08/report.md) and [complete helper qualification](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-render-2026-09-08/runtime-report.md) retain state, cancellation, resource and timing checks.

Themes share collection behavior because independently implemented theme collectors repeated Git work and tied response time to appearance. The [original comparison](https://github.com/wakamex/zsh-theme-bench/blob/main/research/core-theme-benchmark-2026-09-02.md) motivated this separation; [current theme comparisons](PERFORMANCE.md#built-in-prompts-compared-with-omz) measure the implemented result.

## Helper-process boundary

The [in-process experiment](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-runtime-boundary-2026-09-09/report.md) failed child-ownership requirements: direct embedding conflicted with shell child handling, and suppressing that handling broke shell waiting. The passing helper's measured IPC cost was 11.850 microseconds p95. Keeping one helper per shell preserved a simpler passing ownership boundary.

Prompt rendering and shell lifecycle remain local. Cross-shell Git collection is deferred until measurements show material duplicate work or aggregate memory cost, after comparing simpler per-session coalescing and caching. A generic provider framework, shared runtime and in-process replacement are not required parts of the architecture. [Remaining work](FEATURES.md) records the conditions for reconsideration.

## Themes and rendering

Definitions use strict versioned TOML with layout, named styles, bounded literals and supported component settings. The validator rejects unknown fields and invalid layouts. Definitions cannot execute shell code or supply raw terminal controls; the renderer escapes runtime values and emits formatting. [THEMES.md](THEMES.md) documents actual syntax, examples and the four bundled presentations.

The format does not provide a general expression language or dynamic provider registry. A public theme directory is not implemented. [Security boundaries](SECURITY.md) separate data-only themes from executable user configuration and trusted Wsh components.

## Foreground jobs and terminal reporting

`wsh --run -- PROGRAM ARG...` passes exact argument bytes into one interactive Zsh. That shell owns the first foreground job and the subsequent prompt, preserving Ctrl-C, Ctrl-Z and `fg`. The [native foreground qualification](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-foreground-2026-09-08/report.md) tests the boundary. [Foreground integration](FOREGROUND.md) records the original stopped-job failure and the deferred event-protocol question.

Native Zsh emits OSC 7 directory reports and OSC 133 command zones. Wsh's source fixes correct prompt identifiers and restore shell directory reporting after child applications change it. Wsh disables the optional startup terminal query by default, following its measured 500 ms unanswered-query cost. The `WSH_NATIVE_TERMINAL_INTEGRATION` marker lets terminal integrations omit duplicate standard reporters. [Terminal integration](TERMINAL-INTEGRATION.md) records the consumer contract and qualification.

## Profiling and diagnostics

Native profiling records startup boundaries, component work and the initial Git prompt transition. The reporter reads private bounded traces and can recover completed events after interruption. Function mode uses Zsh's zprof. Trace processing stays off the path it measures; experiments compare matching instrumentation and observe editor readiness after ZLE initialization.

[Profiling](PROFILING.md) documents supported commands, attribution, privacy and recovery. [Native profile qualification](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-profile-2026-09-08/report.md), [startup lifecycle](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-lifecycle-2026-09-08/report.md) and [child isolation](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-profile-isolation-2026-09-08/report.md) retain their gates. Doctor evaluates configuration ownership without editing it; [doctor qualification](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-doctor-2026-09-08/report.md) covers that tool.

## Build and package ownership

The [source lock](build/zsh-sources/zsh-cad0d67c-native.json) selects exact upstream bytes, source patches and native inputs. Wsh's source corrections cover terminal reporting, reproducible compiled-function output and highlight ownership metadata; [upstream bug records](UPSTREAM-ZSH-BUGS.md) distinguish confirmed defects and submission status.

The active build and distribution tools no longer require Rust or Cargo. [Build consolidation](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-consolidation-2026-09-10/build-report.md) records the retirement. The installation manifest identifies payload files, source, target, toolchain and dependencies. DNF replaces installed packages; there is no launcher activation record or Wsh self-updater.

Running shells retain their linked executable and bundled modules across package replacement. Autoload functions, external modules and helper protocols require compatible resources or an explicit restart policy before an incompatible release. [Installation and recovery](NATIVE-INSTALLATION.md) define account-shell and removal boundaries.

[DEVELOPMENT.md](DEVELOPMENT.md) owns build and test procedures; [RELEASES.md](RELEASES.md) owns exact-commit validation, reproducible artifacts, provenance and publication. Source RPMs support downstream builds with their own identity. Native package publication still requires an authorized version and release.
