# wsh runtime design

`wsh` provides a measured service and distribution layer around upstream Zsh. It keeps Zsh language semantics, job control, and ZLE editing while supplying curated defaults, tested adapters, shared state providers, and enough profiling to attribute their cost. The first service is a shared structured Git-state runtime between Zsh events and prompt rendering. Its provider adapts the asynchronous precursor worker measured by `zsh-theme-bench`; later provider implementations can change without changing theme definitions. Structured foreground startup and native terminal reporting are accepted features outside the provider boundary. Generic environment state, completion, foreground-job events, pane history, and terminal metadata remain evidence-gated in [`FEATURES.md`](FEATURES.md), [`FOREGROUND.md`](FOREGROUND.md), [`COMPLETION.md`](COMPLETION.md), and [`TERMINAL-INTEGRATION.md`](TERMINAL-INTEGRATION.md).

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

## The accepted post-5.9 Zsh revision supplies tested interfaces

Official release `v0.1.3` uses stable Zsh 5.9.2. Current development pins upstream commit `cad0d67c76e2be7371cf3526b79ea2581810d35a` as one exact Zsh identity after it passed the complete floor, correctness, compatibility, resource, and performance gates. The retained [edge-Zsh result](benchmarks/edge-zsh-2026-09-03/report.md) directly tests current-shell command substitutions, named references, named layered ZLE highlights, and `ZSH_EXEPATH`. Other post-5.9 interfaces remain candidates until a fixture verifies their behavior in the selected revision.

| Zsh feature | Use in `wsh` |
|---|---|
| Named references | Populate caller-owned associative arrays without serializing and reparsing state |
| Namespaced parameter and function names | Group runtime state and reduce collisions with plugins; namespaces are organizational rather than a security boundary |
| Non-forking command substitutions | Capture output from pure Zsh renderers without creating a subshell |
| Named ZLE highlight groups and numeric layers | Compose syntax, selection, search, diagnostic, and mode highlighting with explicit precedence |
| Terminal capability parameters | Centralize terminal feature detection instead of repeating heuristics in themes |
| Native OSC 7 and OSC 133 reporting | Give compatible terminals one shell-owned working-directory, prompt, command, and output lifecycle without injected prompt hooks or prompt-time helpers |
| Cursor form controls | Express editing modes and interactive states through a common presentation service |
| Monotonic high-resolution timing | Drive deadlines, cache ages, command duration, and internal measurements without wall-clock jumps |
| `ZSH_EXEPATH` | Locate the bundled runtime and helper programs |
| GNU-style `zparseopts` | Provide consistent argument parsing for `wsh` commands |

When available in the selected Zsh identity, these features improve the boundary but do not remove the cost of external programs. Field registration and providers remain responsible for avoiding unnecessary work and keeping unavoidable work away from the first editable prompt.

## Native Zsh owns standard terminal reporting

The bundled Zsh emits OSC 7 working-directory reports and OSC 133 prompt and command zones from its native ZLE and command loop. Wsh disables only the optional startup query by default, because an unanswered query added 500 ms in the retained edge-Zsh experiment. The accepted source patch makes directory reporting independent of that query, produces a prompt identifier accepted by Wakterm's real parser, and reasserts the shell's local directory before every editable prompt after child applications may have emitted their own OSC 7 value.

Wsh sets `WSH_NATIVE_TERMINAL_INTEGRATION=1` so a terminal's existing shell script can omit duplicate standard reporters while retaining unrelated integration. Wakterm uses this signal to skip its OSC 7 and OSC 133 paths and keep OSC 1337 user variables. It does not need to parse shell commands, reconstruct arguments, or understand Zsh job control.

The exact first application launched with `wsh -- <command> [arguments...]` runs before the first ordinary editable command, so a one-shot adapter emits its OSC 133 `C` and `D` boundaries around that array. Every later command and prompt marker comes from native Zsh. A general lifecycle bus and shell-specific terminal protocol are not part of this design.

## Existing Zsh configuration remains executable and compatible

`wsh` aims to preserve ordinary Zsh startup behavior for existing `.zshrc` files, Oh My Zsh setups, completion functions, and executable plugins. Compatibility does not mean reimplementing every Oh My Zsh plugin as a `wsh` builtin. Existing code continues to run with normal shell authority, while `wsh` can provide measured replacements for common subsystems.

The default experience targets substring history search, autosuggestions, and syntax highlighting. Each enters separately by pinning, bundling, configuring, and testing an established upstream implementation as a trusted executable component. Reimplementation in Rust or a native module requires a reproduced correctness, composition, or performance problem that the established implementation cannot solve cleanly.

The first accepted default is history substring search from pinned `zsh-users/zsh-history-substring-search` source. The bundle retains that source byte for byte and precompiles it with the paired Zsh. Its adapter loads after `.zshrc`, binds the terminal's advertised Up and Down keys in the active keymap when their existing behavior is ordinary history navigation, and preserves custom bindings. Exact pinned upstream and Oh My Zsh copies are replaced with the bundled runtime definitions after a bounded in-process comparison. Modified or unknown implementations remain active and are reported as external ownership. The redundant `.zshrc` declaration remains until a later doctor result can identify it as safely removable.

The second accepted default is the pinned upstream autosuggestions implementation. Wsh precompiles it and selects its documented manual-rebind mode after user startup and the bundled history widgets are present. This removes the measured per-prompt widget rescan while retaining upstream suggestion semantics and an explicit `_zsh_autosuggest_bind_widgets` path for widgets added later. Exact copies that have not started are replaced; active wrapper stacks, modified implementations, and unknown definitions remain external. Wsh exposes explicit automatic-rebind, synchronous-fetch, and disable settings without introducing a new line editor or widget broker.

The third accepted default is the pinned upstream syntax-highlighting implementation. An ordinary source declaration through Wsh's nested user-startup path sees ZLE as inactive and installs no redraw hooks. Wsh defers clean bundled loading to the first prompt, when ZLE is active, and preserves upstream's redraw-hook design, highlighter selection, and style map. Exact core and active shipped highlighter files can be activated without a second source pass. Modified active files, custom highlighters, incomplete installations, and unknown implementations remain external. This keeps ZLE responsible for editing and highlighting while fixing the reproduced lifecycle failure.

Startup coexistence has explicit ownership. One component owns each prompt renderer, Git collector, lifecycle protocol, and ZLE widget or highlight layer. A `wsh` presentation owns `PROMPT`, `RPROMPT`, its Git provider, and its repaint path. An explicitly selected legacy theme owns its presentation instead of running a second renderer beside `wsh`. Existing plugins keep their unrelated functions, aliases, completions, widgets, and hooks.

`wsh` handles a compatibility case automatically only when detection and treatment are deterministic, local, reversible, and covered by a fixture. If active components have ambiguous or overlapping ownership, the component preserves user behavior and exposes the specific conflict for a focused doctor check. Doctor explains the observed owners and alternatives; it does not silently rewrite arbitrary startup source or make an ambiguous choice.

- A plugin adapter can provide selected lifecycle variables, hook behavior, and loading conventions.
- A migration tool or maintained port can map an existing theme's visual choices into a non-executable `wsh` definition.
- Unmodified themes and plugins remain explicitly executable Zsh configuration outside the `wsh` theme directory, validator, and non-executable guarantee.

An adapter or automatic compatibility rule is accepted when it has a pinned reproducer, tests, and one clear owner. Code that can merely be sourced is not automatically a subsystem that `wsh` should replace.

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

The launcher and release installer remain outside the active release directory and implement bundle listing, verification, installation, selection, and rollback without starting the active Zsh or runtime. Activation writes a bounded launch record derived from the completely verified manifest. Ordinary startup reads only that record, checks required entrypoint metadata, and replaces itself with the selected Zsh through `exec`; it does not retain a manager process or perform update work. Direct bundle activation does not replace either native tool. The explicit update command resolves a canonical exact release and delegates installation to that release's bootstrap, which installs the matching launcher and installer together with the complete release. A package-manager installation leaves those tools to that package manager.

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
- Release-attestation, build-attestation, reproducible-build, interrupted-update, atomic-activation, and offline-rollback tests
- Full-bundle immutability and recovery tests that reject component replacement and keep rollback usable when the active Zsh or runtime cannot start

The Wsh semantic version identifies the complete distribution. The bundled Zsh version and revision identify the shell component selected and tested for that distribution release. `wsh --version` reports the installed launcher version without requiring active state. `wsh version` verifies the active bundle and reports its release or development identity, Wsh and Zsh source revisions, exact Zsh version, target, and bundle digest. The verified manifest retains the complete Zsh build configuration, compiler, patch set, and payload identities. Benchmark artifacts record the executable hash as well as the printed Zsh version so development snapshots cannot be confused.

The current patch queue contains two digest-pinned patches against the selected post-5.9 revision. The terminal-integration patch corrects the native OSC 133 prompt-marker identifier and restores the shell's OSC 7 directory after each completed foreground command. Both failures occur inside the native producer and cannot be corrected by a function or wrapper without installing a second lifecycle owner. The compiled-function patch replaces uninitialized alignment bytes with zeroes so independent builds produce the same `.zwc` bytes without exposing stale heap contents. Both patches have focused reproducers and pass the complete upstream Zsh and Wsh suites. The terminal behavior is tied to the real Wakterm parser, isolated PTY transcripts, process tracing, and the retained [terminal-integration result](benchmarks/native-terminal-integration-2026-09-04/report.md). Further patches remain exceptional so the distribution can continue following upstream. [`IMPLEMENTATION.md`](IMPLEMENTATION.md) fixes the first target, source release, bundle layout, language boundary, theme scope, and milestone thresholds.
