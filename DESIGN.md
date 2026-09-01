# wsh runtime design

`wsh` provides a measured service and distribution layer around upstream Zsh. It keeps Zsh language semantics and ZLE editing while supplying curated defaults, tested adapters, shared state providers, and enough profiling to attribute their cost. The first service is a shared structured Git-state runtime between Zsh events and prompt rendering. Its provider adapts the asynchronous precursor worker measured by `zsh-theme-bench`; later provider implementations can change without changing theme definitions. Foreground startup, generic environment state, completion, and terminal integration are outside this first provider boundary and remain evidence-gated in [`FEATURES.md`](FEATURES.md), [`FOREGROUND.md`](FOREGROUND.md), [`COMPLETION.md`](COMPLETION.md), and [`TERMINAL-INTEGRATION.md`](TERMINAL-INTEGRATION.md).

## State collection and rendering have separate contracts

```text
Zsh events
    |
    v
registered field requirements
    |
    v
resident runtime and providers
    |
    v
complete versioned snapshot
    |
    v
trusted prompt components configured by a non-executable theme
    |
    v
one composed prompt, with at most one asynchronous repaint per transition
```

A trusted prompt component registers the fields selected by the active theme definition. The runtime collects the union of active requirements once per relevant state transition and publishes a complete snapshot. Requirements can change when themes or prompt components are reconfigured.

A minimal theme definition conceptually selects the Git prompt component and fields:

```text
theme-version: 1
left: cwd, git, prompt-character
git.fields: branch, staged, modified, untracked
git.staged-marker: " +"
git.modified-marker: " !"
git.untracked-marker: " ?"
```

A trusted Git prompt component queries a caller-owned associative array internally. The theme cannot supply executable Zsh:

```zsh
wsh_component_git_render() {
  local -A state
  prompt_query state

  [[ -n $state[git.branch] ]] && print -nr -- "$state[git.branch]"
  (( state[git.staged] )) && print -nr -- " +"
  (( state[git.modified] )) && print -nr -- " !"
  (( state[git.untracked] )) && print -nr -- " ?"
}
```

The component does not know which provider produced the values and does not launch repository commands. The definition can select and configure that component only through its versioned schema.

## Themes are data and prompt components are trusted code

The public theme surface is a versioned non-executable definition format. Definitions arrange trusted prompt components, select named styles, provide bounded validated literals, choose declared variants, and request typed provider fields. The format has no general expression evaluator, function definition, command substitution, hook registration, file include, environment lookup, network reference, native extension, or raw prompt and terminal escape mechanism.

Provider strings are untrusted even when their provider is part of `wsh`. Prompt components render them through context-specific encoders, and only the renderer emits Zsh prompt escapes or terminal controls. Named operations represent styles, line breaks, hyperlinks, and other terminal behaviors without exposing their byte sequences to a definition.

The definition validator enforces byte, segment, nesting, output, provider-requirement, and render-time limits. The runtime attributes provider work and render cost to the active theme, but a definition cannot add authority beyond the prompt components it selects. Trusted prompt components are executable runtime code and enter through the ordinary source, benchmark, release, and update process.

The theme directory accepts every definition version that passes mechanical schema, namespace, metadata, resource, and terminal-safety checks. Visual taste, duplication, popularity, and optional field cost do not determine admission. Bundled and recommended views are curated separately. [`SECURITY.md`](SECURITY.md) defines the exact admission, installation, hostile-input, and update contracts.

## The first wsh provider has a bounded Git field scope

The first `wsh` Git contract covers fields already produced by the benchmarked source collector:

```text
git.root
git.branch
git.detached_sha
git.exact_tag
git.staged
git.modified
git.untracked
git.ahead
git.behind
git.operation
git.worktree
```

Field definitions and fixtures belong to `wsh`, not to a particular collector. The initial benchmark established rendered semantics only for clean, staged, modified, untracked, and detached-HEAD scenarios. Ahead, behind, exact tags, and repository operations are present in the current collector's advertised scope but require their own fixtures before `wsh` claims them as validated service behavior.

Additional fields remain explicit and lazy. Stash count, commit age, conflict classification, submodule detail, or other expensive state is added only with a definition, provider support, fixtures, and a requesting renderer. A broader renderer does not silently increase the cost paid by every renderer.

Collectors own:

- Cache keys and invalidation
- External process execution
- Optional lock suppression
- Asynchronous scheduling
- Deadlines and cancellation
- Result and schema versioning
- Error and unsupported-state handling
- Snapshot freshness metadata
- Snapshot publication

Themes consume completed snapshots. A snapshot can remain visible while its replacement is collected, but partial results do not mutate it in place.

Every accepted provider exposes measurements through the same runtime boundary: request identity, requested fields, queue and execution duration, cache decision, external process count, cancellation reason, result age, publication, and repaint cause. Values that can disclose command text, arbitrary paths, environment contents, credentials, or provider payloads are omitted or redacted by default. A provider that cannot be measured cannot satisfy the feature admission gates.

## The first wsh provider adapts the benchmarked worker

The manager and shared runtime are implemented in Rust. A thin trusted Zsh adapter owns only the interfaces that must live in the shell process: hooks, ZLE callbacks, prompt installation, snapshot transfer, and repaint requests. The initial Rust Git provider adapts the semantics and lifecycle demonstrated by the precursor worker, including staged asynchronous results, a bounded identity wait, cancellation, refresh coalescing, stale-result rejection, process cleanup, optional-lock suppression, and repaint-on-change behavior.

Generalizing it requires separating its structured Git result from its current glyph and prompt decisions. The provider publishes the existing field scope while trusted prompt components interpret the active definition's validated choices about whether `main` is hidden, whether a branch appears only after it changes, and which symbols and named styles represent each state.

The first implementation remains above the Zsh engine. The Rust runtime communicates with the thin Zsh adapter through a small versioned protocol. A dynamically loaded Zsh module is justified only if profiling isolates meaningful cost in adapter dispatch, serialization, or copying. External Git latency does not establish that the adapter needs native in-process code.

## Git provider implementations remain replaceable

[`gitstatusd`](https://github.com/romkatv/gitstatus) demonstrates a useful provider shape: a long-lived native process accepts directory and request identifiers, retains repository state in memory, and returns machine-readable status. Its bindings expose branch, commit, tag, ahead, behind, stash, conflict, staged, unstaged, untracked, and repository-operation data.

`wsh` can adapt gitstatusd behind its field contract and compare it with the initial process-backed `wsh` provider. The gitstatus project states that support is limited, no new features are planned, and most bugs will remain unfixed, so reuse does not transfer ownership of semantics, fixtures, supervision, or fallback behavior.

A later provider could use system Git, libgit2, a maintained fork, or a purpose-built scanner. The benchmark does not establish persistence as the required implementation. The choice follows measurements of warm and cold latency, CPU time, filesystem work, semantic parity, memory, and invalidation behavior on repositories of different sizes. Renderers do not change when the provider changes.

[Nushell's persistent-plugin results](https://www.nushell.sh/blog/2024-04-02-nushell_0_92_0.html) demonstrate that residency can amortize meaningful process startup, but also that persistence introduces idle lifetime, cleanup, protocol migration, retained memory, and crash behavior. `wsh` therefore begins with the smallest measured worker. A provider becomes resident only when the short-lived path's cold-start cost is isolated, an idle-expiration policy is tested, and the resident comparison improves the accepted workload without weakening cleanup or fallback.

## Prompt transitions follow observable rules

1. The first editable prompt does not wait for slow optional fields.
2. A collector publishes a complete versioned replacement.
3. Completed asynchronous work is coalesced into at most one repaint for a state transition.
4. A repaint occurs only when the rendered result changed.
5. Previous state can remain visible during collection, but its freshness is explicit and bounded.
6. Active field requirements determine collection cost.
7. Starting a command or changing context cancels work that can no longer produce a valid snapshot.
8. Bundled renderers do not launch repository commands directly.

These rules are tested through both deterministic protocol tests and interactive terminal tests because worker lifecycle and ZLE integration have different failure modes.

## Post-5.9 Zsh features may simplify later runtime work

The first bundle uses stable Zsh 5.9.2 and cannot assume interfaces present only in the current development branch. The development revision is benchmarked separately when one of the following capabilities could remove measured adapter work or fix a reproduced problem. It enters an official bundle only as one exact tested Zsh identity.

| Zsh feature | Use in `wsh` |
|---|---|
| Named references | Populate caller-owned associative arrays without serializing and reparsing state |
| Namespaced parameter and function names | Group runtime state and reduce collisions with plugins; namespaces are organizational rather than a security boundary |
| Non-forking command substitutions | Capture output from pure Zsh renderers without creating a subshell |
| Named ZLE highlight groups and numeric layers | Compose syntax, selection, search, diagnostic, and mode highlighting with explicit precedence |
| Terminal capability parameters | Centralize terminal feature detection instead of repeating heuristics in themes |
| Cursor form controls | Express editing modes and interactive states through a common presentation service |
| Monotonic high-resolution timing | Drive deadlines, cache ages, command duration, and internal measurements without wall-clock jumps |
| `ZSH_EXEPATH` | Locate the bundled runtime and helper programs |
| GNU-style `zparseopts` | Provide consistent argument parsing for `wsh` commands |

When available in the selected Zsh identity, these features improve the boundary but do not remove the cost of external programs. Field registration and providers remain responsible for avoiding unnecessary work and keeping unavoidable work away from the first editable prompt.

## Compatibility uses explicit adapters

`wsh` can support selected Oh My Zsh plugins and reproduce theme appearances without claiming the entire Oh My Zsh maintenance surface.

- A plugin adapter can provide selected lifecycle variables, hook behavior, and loading conventions.
- A migration tool or maintained port can map an existing theme's visual choices into a non-executable `wsh` definition.
- A legacy escape hatch can source unmodified code only as explicitly executable Zsh configuration outside the `wsh` theme directory, validator, and non-executable guarantee.

An adapter is accepted when it has tests and an owner. Code that can merely be sourced is not automatically supported.

## Release bundles keep one exact Zsh build and runtime together

A wsh release bundle is the complete runnable distribution for one supported target. It contains the exact Zsh binary and modules, the matching wsh runtime, trusted prompt components and providers, schemas, bundled themes and adapters, and a manifest that identifies every input and payload file. The common release identifies one Zsh source revision and every common or target-specific patch, while each target records its build configuration, toolchain, and binary digests.

The release-to-Zsh mapping is exact but not mathematically one-to-one. Every wsh release maps to one Zsh source and build identity per target, while multiple wsh releases may reuse that identity when only the wsh runtime changes. Any change to the Zsh revision, patches, configuration, toolchain-sensitive output, or target binary creates a new wsh release candidate and reruns the complete validation suite.

Installed release directories are immutable. Zsh, the runtime, a trusted prompt component, a schema, or a bundled adapter is never replaced independently inside one. Updating any component installs a new complete directory, verifies it, and atomically changes the active selection. Rollback selects the previous complete directory rather than reconstructing an older combination of components.

```text
wsh installation
├── stable manager and launcher
├── immutable release bundles
│   ├── exact Zsh binary and modules
│   ├── matching wsh runtime and trusted prompt components
│   └── schemas, bundled definitions, adapters, and manifest
└── mutable user state
    ├── configuration and local overrides
    ├── third-party theme definitions
    ├── history
    └── caches and traces
```

The manager and launcher remain outside the active release directory and implement bundle listing, verification, selection, and rollback without starting the active Zsh or runtime. A bundle update does not silently replace the manager. A standalone manager update is a separate signed operation, while a package-manager installation leaves manager updates to that package manager.

Official wsh-managed bundles always use their recorded Zsh build. A development or compatibility command may test an external system Zsh, but that combination is outside the official bundle's correctness, performance, reproducibility, and rollback guarantees.

## Candidate snapshots pass distribution and runtime gates

Every candidate Zsh snapshot should pass:

- The upstream Zsh test suite
- `wsh` startup and interactive smoke tests
- Provider and renderer API contract tests
- Theme-schema, hostile-value, terminal-control, and resource-bound tests
- Clean, staged, modified, untracked, and detached fixtures for the first provider, plus fixtures for each additional advertised field
- First-editable and final-state latency measurements
- Repaint and external-process limits
- Optional-lock checks
- Signed-manifest, reproducible-build, interrupted-update, atomic-activation, and offline-rollback tests
- Full-bundle immutability and recovery tests that reject component replacement and keep rollback usable when the active Zsh or runtime cannot start

The binary reports the upstream commit, build configuration, compiler, applied patch set, and distribution version. Benchmark artifacts record the executable hash as well as the printed Zsh version so development snapshots cannot be confused.

The initial patch queue is empty. If a required capability cannot be implemented through functions, hooks, ZLE widgets, loadable modules, or a worker, `wsh` can carry a narrow patch tied to a reproducer and benchmark. Patches remain exceptional so the distribution can continue following upstream. [`IMPLEMENTATION.md`](IMPLEMENTATION.md) fixes the first target, source release, bundle layout, language boundary, theme scope, and milestone thresholds.
