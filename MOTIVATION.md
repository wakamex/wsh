# wsh motivation

`wsh` turns Git prompt performance and correctness machinery currently hand-built behind individual Zsh themes into a shared service. Non-executable theme definitions format structured Git state through trusted prompt components instead of spawning Git commands, managing asynchronous workers, invalidating caches, coordinating repaints, or receiving shell authority. `wsh` packages that runtime with a pinned, tested Zsh build so the shell and its integration API update and roll back together.

The product goal is a current, curated Zsh experience with the useful conventions people reach for Oh My Zsh to obtain, but without requiring users to assemble a framework, inherit unmaintained theme machinery, grant appearance files shell authority, or accept each theme's collector performance. It should provide Fish-like interactive usability and measured defaults while retaining compatibility with existing shell commands, Zsh scripts, completion functions, and selected plugins. `wsh` remains a service and distribution layer around upstream Zsh. It does not become another shell language or line editor.

This direction came from benchmarking existing themes, not from an assumption that every prompt needs a new framework. The benchmark found that choosing a theme also chooses its Git-state implementation or integration path. Source inspection showed why: literal Oh My Zsh helper calls inherited shared asynchronous behavior, wrapped helpers could escape registration, direct collectors bypassed shared improvements, and custom caches owned their own invalidation.

## Benchmarking exposed theme-owned collector machinery

The [`zsh-theme-bench` report](https://github.com/wakamex/zsh-theme-bench/blob/main/research/core-theme-benchmark-2026-09-01.md) compared representative prompt architectures in fresh interactive terminals against the same 1,000-file Git fixture. Each target ran 20 timed clean, tracked-dirty, and untracked transitions, followed by staged and detached-HEAD checks. The `wsh` precursor, shown as `wakamex` in that report, had the lowest worst retained settled latency among targets that passed every applicable semantic check at 7.211 ms, while agnoster reached an 85.881 ms first-prompt maximum.

The median results show how tightly theme selection is currently coupled to collection behavior:

| Theme path | First editable prompt, ms | Settled prompt, ms | Git processes per transition | Collection design |
|---|---:|---:|---:|---|
| `wsh` precursor | 1.4-1.5 | 1.4-6.9 | 1 | Custom asynchronous worker with one status scan |
| Oh My Zsh `robbyrussell` | 6.1-6.7 | 27.9-28.9 | 5 | Shared Oh My Zsh asynchronous helper |
| Oh My Zsh `agnoster` | 79.4-81.4 | 79.4-81.4 | 16 | Theme-owned synchronous Git commands |
| Pure | 10.7-11.5 | 23.5-24.5 | 6 | Theme-owned native-Zsh asynchronous worker |
| Powerlevel10k Pure preset | 11.9-12.4 | 12.6-13.0 | 0 | Persistent `gitstatusd` provider |

The accompanying [`direct Git inspection`](https://github.com/wakamex/zsh-theme-bench/blob/main/research/direct-git-inspection-2264a8042763.md) found 65 direct Git invocation sites across 28 Oh My Zsh themes. Twenty-seven themes connected at least one site to an active prompt or hook. The review identified repeated repository detection, duplicate status scans, synchronous commit-age lookups, optional Git locks, async registration gaps, and incomplete cache invalidation.

The implementations make different tradeoffs. The `wsh` precursor was correct in its advertised scope across the five tested scenarios, used one optional-lock-safe Git process per transition, and returned an editable prompt near the raw control. Oh My Zsh's shared helpers preserved the tested semantics and supplied asynchronous execution and lock suppression, but used five Git processes and settled around 28-45 ms in the measured themes. Pure preserved its tested semantics but used six Git processes, five without optional-lock suppression, and settled around 24 ms. Powerlevel10k served broad state without observed Git child processes during measured transitions because collection work occurred inside its resident `gitstatusd` process, not because collection was free.

The benchmark evidence is scoped to the pinned targets, one host, one 1,000-file fixture, 20 timed clean, dirty, and untracked transitions, and one staged and detached-HEAD check. Within that scope, it shows that theme selection currently selects both presentation and collection behavior. The renderer-independent service is the proposed response, not a result established by the benchmark.

That precursor worker supplies the clearest starting implementation for `wsh`. It contains a custom staged protocol, descriptor callbacks, cancellation, refresh coalescing, optional-lock suppression, direct repository metadata reads, status parsing, and repaint logic. Powerlevel10k demonstrates a different successful resident-provider approach. Oh My Zsh demonstrates that themes using literal shared helpers can inherit framework improvements without changing theme code, while direct theme commands and helpers hidden behind wrappers do not automatically inherit that path.

These mechanisms should not have to be rewritten behind every visual design. Fixing individual themes remains useful for their users, but it leaves the next theme author responsible for the same collector lifecycle and correctness problems.

## Shared state separates performance from presentation

`wsh` gives collectors ownership of discovery and trusted prompt components ownership of rendering. A non-executable theme definition conceptually selects components and the state they display:

```text
theme-version: 1
left: cwd, git, prompt-character
git.fields: branch, staged, modified, untracked, ahead, behind
git.dirty-marker: " *"
```

The first serialization is strict versioned TOML. The contract is data-only: a definition references only versioned prompt components and typed fields, and cannot run Git, register hooks, source code, read files or environment variables, access the network, or emit raw prompt and terminal controls.

Anyone can publish a definition to the open-submission directory. Every version that passes the schema, namespace, bounded-resource, and terminal-safety checks is listed without a maintainer deciding whether its appearance is original, popular, or worth maintaining. Bundling and recommendations remain separate curated views. The full admission and trust contract is in [`SECURITY.md`](SECURITY.md).

The runtime collects the union of registered requirements once per relevant state transition. The first `wsh` Git provider covers repository identity, branch or detached state, staged, modified, untracked, ahead, behind, and repository-operation state. Stash count, commit age, conflict classification, and other fields are later explicit requirements rather than costs silently imposed on every renderer. Switching to a broader renderer can request supported additional fields without replacing the collector or changing the meaning of fields already in use.

`wsh` defines one semantic contract for repository state across bundled themes. Collectors own external processes, cache identity and invalidation, deadlines, cancellation, result versioning, unsupported states, and snapshot publication. Themes receive completed versioned values and do not depend on whether those values came from a Zsh builtin, a direct file read, a short-lived worker, `gitstatusd`, or another provider.

The user-visible contract is small:

1. The first editable prompt does not wait for slow optional fields.
2. A collector publishes a complete versioned snapshot instead of a partially updated set of fields.
3. Completed asynchronous work causes at most one composed repaint for a state transition.
4. A repaint occurs only when the rendered prompt changed.
5. Previous state may remain visible during collection, but its age is identified and bounded.
6. Unrequested fields are not collected.
7. Bundled themes do not launch repository commands directly.

Prompt latency, final-state latency, repaint count, process count, and repository correctness therefore become properties of the runtime rather than accidental properties of a theme.

## Profiling and tracing make performance claims reproducible

Measurement is part of the product rather than a separate maintainer-only benchmark. `wsh` should be able to explain startup, prompt, provider, repaint, completion, history, and terminal-integration cost well enough to reproduce a regression and judge an intervention.

The initial instrumentation surface should provide human-readable summaries and machine-readable records for:

- Zsh startup and configuration phases
- Loaded adapters, themes, and completion functions
- Provider requests, requested fields, deadlines, cancellation, cache reuse, and snapshot age
- External process count and duration
- First-editable and settled prompt latency
- Repaint causes and coalescing
- Ordered lifecycle events and emitted terminal protocol components

Timing uses a monotonic clock. Trace records carry the `wsh` version, Zsh source revision, executable hash, enabled components, and workload identity so results from different builds are not silently combined. Full command lines, arbitrary environment values, credentials, and unredacted provider payloads are excluded by default. Instrumentation overhead is measured, tracing is off by default, and benchmark gates compare the same workload with the same trace mode before and after a change.

[Fish's startup profiler and execution tracing](https://fishshell.com/docs/current/relnotes.html) demonstrate that this can be a normal shell diagnostic rather than an external sampling exercise. `wsh` extends that idea across the service boundaries it owns, including asynchronous providers and terminal events that ordinary function timing cannot attribute.

## The distribution keeps the shell and runtime compatible

The shared collector boundary could be implemented as a framework on an operating-system Zsh. `wsh` is a distribution because it also wants a known shell API, reproducible integration tests and release artifacts, authenticated updates, and atomic rollback of the shell and runtime.

Zsh 5.9 was released in 2022, followed by maintenance releases in 2026, while the next feature release remains under development. Upstream [`NEWS`](https://github.com/zsh-users/zsh/blob/master/NEWS) describes named references, namespaces, non-forking command substitutions, layered ZLE highlighting, terminal capability reporting, monotonic timing, job-control improvements, and other changes merged after 5.9. These features make the service boundary cleaner, but operating-system packages reasonably favor released versions.

`wsh` builds the signed upstream Zsh source release corresponding to an exact revision, runs the upstream suite and its interactive runtime tests, and records the archive, signature identity, source revision, build configuration, compiler, patch set, and executable hash. Each official unsigned payload must reproduce byte-for-byte in two isolated clean builds before its digest enters a signed release manifest. The default channel can advance only through an explicit update when a candidate passes those gates. A failed or interrupted candidate does not replace the accepted bundle, and the previous verified bundle remains available for offline rollback.

The mapping is deliberately from a wsh release to one exact Zsh identity, not a requirement that every wsh release use a different Zsh revision. Runtime-only releases can reuse the same Zsh build. A new Zsh revision, patch set, build configuration, or target binary always produces a new complete wsh bundle and reruns the upstream, integration, prompt, provider, compatibility, security, and performance gates. Neither Zsh nor the runtime changes inside an installed bundle.

A small manager and launcher downloads and selects complete prebuilt wsh bundles and retains a recovery path outside them. Zsh compilation occurs in the release pipeline, not on the user's machine. The manager has no general package index, formula language, dependency solver, or authority over unrelated software. Configuration, third-party theme definitions, history, and caches remain mutable user state outside release directories. This lets an update or rollback replace the tested distribution without overwriting personal state, and it lets rollback work even when the newly selected Zsh or runtime cannot start.

Bundling prevents a runtime written for one upstream snapshot from silently running against different namespace, named-reference, ZLE, or timing behavior. It also lets `wsh` own a compatibility decision when an unreleased upstream behavior changes. The project does not need to fork the Zsh language or execution engine to obtain that control.

## The first release makes one collector reusable

The first release is useful when it can:

1. Launch a pinned current Zsh build without replacing the system shell.
2. Report complete source and binary provenance.
3. Load the `wsh` runtime and its initial Git provider.
4. Serve a versioned Git snapshot through the theme API.
5. Render one minimal and one broad non-executable theme definition through trusted prompt components.
6. Provide the initial `wsh` Git field scope and pass the five benchmarked clean, staged, modified, untracked, and detached scenarios.
7. Show that switching non-executable theme definitions changes formatting and requested fields without duplicating collection work.
8. Meet first-editable latency, settled-state latency, repaint, external-process, and optional-lock limits.
9. Produce a versioned profile and trace that attribute those measurements without recording command text or secrets by default.
10. Reject hostile definitions and provider values without executing content or emitting unintended terminal controls.
11. Verify a signed reproducible bundle, activate it atomically, and roll back the complete Zsh-runtime pair when a candidate fails.

This release cleans up and generalizes the hand-coded performance work that motivated the benchmark. Upstream Zsh remains the shell, `wsh` owns the tested distribution and shared interactive runtime, providers own state discovery, and themes own presentation. The fixed first-target choices and thresholds are in [`IMPLEMENTATION.md`](IMPLEMENTATION.md).

## Completion is a later provider experiment

Generated completion files repeat command models in shell code much as themes repeat state collectors. The first experiment uses Wakterm's existing mux and live Clap model while Zsh retains candidate presentation and selection. A generic broker is considered only if another application later demonstrates the same lifecycle need. This is not a requirement for the first release. Its baseline, protocol, and comparison are in [`COMPLETION.md`](COMPLETION.md).

Other candidates must pass a reproducible correctness or performance comparison and produce a concrete consumer improvement before entering the roadmap. Those evidence gates are in [`FEATURES.md`](FEATURES.md). The foreground-child counterfactual is in [`FOREGROUND.md`](FOREGROUND.md), and the terminal contract is in [`TERMINAL-INTEGRATION.md`](TERMINAL-INTEGRATION.md).

## Initial scope remains narrow

The initial project does not:

- Fork the Zsh parser, language, execution engine, or job-control implementation
- Reimplement Git inside the shell
- Promise that every upstream commit will be published
- Promise automatic structured completion for unregistered third-party commands
- Bundle every Oh My Zsh theme or plugin
- Replace ZLE or introduce another interactive editor
- Introduce another shell language or structured pipeline language
- Make visual style part of the state engine
- Source executable files as `wsh` themes or treat directory admission as permission to execute code
- Update installed code during interactive shell startup
- Introduce a native module before measurements isolate a meaningful Zsh-level cost
- Treat an unreleased Zsh behavior as stable without owning a compatibility decision

The runtime design, provider boundary, compatibility policy, and validation rules are specified in [`DESIGN.md`](DESIGN.md).
