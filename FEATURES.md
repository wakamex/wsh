# wsh feature evidence

The first `wsh` release remains the benchmarked shared Git-state service rendered through non-executable theme definitions and distributed through verified reproducible updates. Later features enter the roadmap only when a reproducible current weakness and a concrete consumer improvement justify them. Wakterm supplies useful candidate workloads, but implementation size or architectural appeal alone does not establish that `wsh` should own a solution.

## Admission requires an observed weakness and a passing intervention

A candidate becomes an accepted `wsh` feature only after its investigation records:

1. A runnable baseline reproducer against the current implementation.
2. An observable correctness failure or a measured cost such as latency, process count, repeated parsing, installed size, or retained memory.
3. The cheapest counterfactual that could solve the problem in its current owner without adding a `wsh` abstraction.
4. A `wsh` intervention only when the counterfactual fails or leaves a reusable measured problem.
5. A concrete consumer result such as deleted integration code, corrected restore behavior, fewer processes, lower latency, or a smaller generated artifact.
6. A regression test that compares the accepted path with the original baseline.

Source size is a useful discovery signal and deletion can be a concrete maintenance result, but line count by itself does not prove a performance or correctness problem. A new daemon, database, protocol, or compatibility layer requires evidence that a smaller adapter cannot provide the same result.

Profiling and tracing are accepted enabling capabilities because every admission gate depends on attributable measurements. They do not justify another feature by themselves. A profile must identify the build, workload, enabled components, external processes, provider work, prompt transitions, repaints, and terminal events while excluding command text and secrets by default. The same workload is measured with the same instrumentation mode before and after an intervention, and instrumentation overhead is measured separately.

## Current evidence ranks investigations rather than promises

| Investigation | Current evidence | Cheapest missing experiment | Result required for adoption |
|---|---|---|---|
| Shared Git state | The pinned `zsh-theme-bench` workload measured correctness, prompt latency, process count, optional-lock behavior, and repeated collection across theme paths | Implement the renderer-independent provider and rerun the same fixtures and transitions | Two renderers reuse one collector while meeting the documented semantic and performance gates |
| Non-executable theme definitions | Oh My Zsh [sources selected theme files](https://github.com/ohmyzsh/ohmyzsh/blob/master/oh-my-zsh.sh), and its 2026 [prompt-injection advisory](https://github.com/ohmyzsh/ohmyzsh/security/advisories/GHSA-x96c-8w82-wf96) identifies ten themes that bypassed a shared escaping fix through separate Git paths | Render the two first-release themes through a data-only schema and run hostile definitions and provider values through the validator and PTY harness | Theme choice changes presentation and field requirements without adding shell, process, file, network, or raw terminal-control authority |
| Verified reproducible bundles | Oh My Zsh [checks for updates during initialization](https://github.com/ohmyzsh/ohmyzsh/blob/master/tools/check_for_upgrade.sh) and supports [prompt, automatic, reminder, background, and disabled modes](https://github.com/ohmyzsh/ohmyzsh/wiki/Settings#update-settings); `wsh` already requires a pinned shell-runtime pair and rollback | Trace startup, build each development bundle twice from pinned inputs, authenticate exact hashes through GitHub build and immutable-release attestations, reject replacement of an individual component, interrupt every activation phase, and test manager-side offline rollback with a broken active bundle | Startup performs no update network or mutation work, official GitHub Release bundles reproduce byte-for-byte, each release maps to one exact Zsh build per target, tampering is rejected, activation is atomic, and the previous verified bundle remains usable |
| Profiling and tracing | Feature admission already requires measurements that ordinary shell timing cannot attribute across asynchronous providers, repaints, child processes, and terminal events | Add versioned human-readable and machine-readable startup, prompt, provider, process, repaint, and lifecycle traces; measure disabled and enabled overhead | A benchmark regression can be assigned to one component and the recorded workload can be compared across exact builds without exposing command text or secrets by default |
| Foreground child followed by a prompt | Wakterm currently reconstructs a provider argument vector as quoted shell text and has encountered restore, job-control, and suspension workarounds | Compare the current wrapper with the exact positional-argument counterfactual in [`FOREGROUND.md`](FOREGROUND.md) | Add a `wsh` contract only if the local wrapper cannot preserve argv, signals, process groups, suspension, reaping, and prompt return |
| Ordered lifecycle and terminal sequences | Wakterm injects a 573-line Bash and Zsh integration that manipulates hooks, invokes helper commands, and emits OSC 7, OSC 133, and OSC 1337 | First make the Wakterm script idempotent, cache stable values, remove full command publication, emit OSC 7 directly, and use native hooks; then compare a `wsh` lifecycle only if measured duplication remains | Wakterm omits the injected script for `wsh` only when `wsh` already owns lifecycle for another accepted feature and preserves semantics with zero added per-prompt child processes or another measured improvement |
| Wakterm dynamic completion | Generated Wakterm assets contain 9,246 lines and 404,616 bytes across Bash, Fish, and Zsh, and issue 41 records duplication of the command tree | Compare pruned static generation, direct `CompleteEnv`, and the existing Wakterm mux for cold and warm latency, correctness, timeout, fallback, and installed size | Choose the smallest passing path; the mux is used only if startup dominates and it preserves candidates with bounded timeout and immediate fallback |
| Stable pane identity and bounded history | Wakterm exports a numeric `WAKTERM_PANE`, but restored panes receive new IDs | Persist a logical token, test a roughly 10-line direct `fc -p` integration, and then test any proposed `wsh` integration | Wakterm supplies the token regardless; `wsh` is adopted only if reusable bounded selection, pruning, or lifecycle behavior improves on the local script |
| Private history | [Fish has needed fixes around in-memory private history](https://fishshell.com/docs/current/relnotes.html), and command text can otherwise reach pane files, indexes, traces, or terminal metadata through independent integrations | Start a fresh memory-only history context, enter sentinel commands, exit normally and by signal, and inspect every configured durable sink and trace | Private commands remain available only during the private context, never reach durable history or adapters, and do not appear in default diagnostics |
| Terminal compatibility doctor | Shell-side lifecycle failures are reproducible from a PTY transcript, while [Fish has also needed terminal-specific OSC 133 and terminal-query workarounds](https://fishshell.com/docs/current/relnotes.html) | Compare passive inspection, an isolated diagnostic shell, bounded reply-producing probes, and a reproduced known terminal quirk | Diagnose shell-side failures directly and issue component-level terminal recommendations only from observed behavior or a versioned reproduced compatibility rule |
| Allowlisted pane metadata | Wakterm can publish a complete command line while its navigator commonly lacks branch state for an ordinary shell pane | Remove unused variables and compare navigator-only cached Git sampling with publishing the existing `wsh` Git snapshot | Use `wsh` only if it avoids a measured Wakterm Git query while populating branch promptly and removing full command text |

The foreground workaround is the highest-priority correctness investigation, not an accepted `wsh` interface. Ordered lifecycle has the largest concrete integration replacement opportunity but first gets a Wakterm-local idempotence and zero-child-process counterfactual. Completion has a measured artifact-size problem but still needs latency and correctness results. Pane identity requires a Wakterm fix regardless, while `wsh` history still has to beat the small direct `fc -p` integration.

## Foreground startup begins with a local counterfactual

Wakterm should first pass the exact provider argument vector through positional shell parameters rather than serialize it with shell quoting. The comparison and job-control assertions are specified in [`FOREGROUND.md`](FOREGROUND.md). If that local change works, Wakterm owns the fix and `wsh` does not add a launcher. If it cannot provide correct interactive job control, the failed cases define the smallest possible `wsh` contract.

## Ordered lifecycle must replace measured integration work

The proposed phases remain small:

```text
chpwd
pre_prompt
editor_ready
pre_exec
post_exec
```

One owner can translate them into prompt repainting, OSC 7, and OSC 133. Before accepting the feature, the Wakterm baseline must identify duplicate or misplaced markers, hook-order failures, prompt-time child processes, or measurable latency. The accepted result should let Wakterm skip its injected integration when launching `wsh`, not merely install a second lifecycle layer beside it.

Autoloaded Zsh functions and existing hook arrays are the first implementation. A general event bus or cross-process service remains unjustified until a measured subscriber requires one.

## Completion starts as a Wakterm endpoint

The first completion architecture is a Zsh adapter calling a Wakterm-owned mux endpoint backed by Wakterm's live Clap model. The application remains authoritative for command structure, and Zsh remains authoritative for matching, grouping, display, and selection. A generic broker becomes a candidate only after a second application demonstrates the same lifecycle need. [`COMPLETION.md`](COMPLETION.md) defines the comparison.

Any dynamic path has hard execution bounds before it can be accepted: one request per editor generation, cancellation when the buffer changes, stale-result rejection, a deadline, candidate and byte limits, provider process limits, bounded caching with explicit invalidation, and immediate native fallback. These are safety properties of the Wakterm experiment, not evidence for a generic broker.

## Pane history uses shell state and terminal identity

The terminal owns a durable logical pane token. `wsh` uses it only to choose a bounded native Zsh history context and file. Up, Down, and ordinary incremental search stay in bounded process memory; no database query enters the editor hot path. Atuin or a derived index can provide broader structured search only when that separate need is demonstrated. [`TERMINAL-INTEGRATION.md`](TERMINAL-INTEGRATION.md) defines the contract and restore test.

Private history is an orthogonal persistence policy. Entering private mode creates a fresh bounded in-memory context, disables durable history adapters for that context, and discards it on exit. It does not claim forensic erasure from process memory. Transitions, signals, trace output, and independent terminal metadata are part of its correctness test.

## Fish and Nushell supply contract tests rather than a new product scope

[Fish's design](https://fishshell.com/docs/current/design.html) validates enabled interactive defaults and asynchronous hot-path I/O, while its [terminal contract](https://github.com/fish-shell/fish-shell/blob/master/doc_src/terminal-compatibility.rst) and [release notes](https://fishshell.com/docs/current/relnotes.html) document native OSC 7 and OSC 133 integration, built-in profiling, and tracing. Historical Fish failures involving an [unbounded multi-million-file completion](https://github.com/fish-shell/fish-shell/issues/2771) and a [multi-process Git prompt](https://github.com/fish-shell/fish-shell/issues/7871) supply adversarial workloads for candidate limits, but do not establish current Fish performance. Nushell validates [structured completion candidates](https://www.nushell.sh/book/custom_completions.html), [ordered hooks](https://www.nushell.sh/book/hooks.html), [bounded completion caching and SQLite history isolation](https://github.com/nushell/nushell/blob/main/crates/nu-config/default_files/doc_config.nu), and [resident providers with idle expiration](https://www.nushell.sh/blog/2024-04-02-nushell_0_92_0.html). Its documented [external-command schema limitations](https://www.nushell.sh/book/externs.html), [runaway external-completer reproducer](https://github.com/nushell/nushell/issues/13201), [hook-order correction](https://www.nushell.sh/blog/2025-09-02-nushell_0_107_0.html), plugin migration cost, and [large-value copy regression](https://www.nushell.sh/blog/2026-08-15-nushell_v0_115_0.html) define failure cases `wsh` should test without adopting Nushell's language or data model.

The resulting boundary remains narrow: Zsh and ZLE own parsing and editing, applications own their command models, terminals own rendering and pane state, and `wsh` owns only measured shared services and the diagnostics needed to evaluate them.

## Promising deferred candidates require their own reproducers

| Candidate | Evidence required before design work |
|---|---|
| Lazy provider registration | A second provider whose eager parsing or startup has measurable cost; the counterfactual is conventional Zsh autoloading without a registry service |
| Resident provider idle expiration | A provider whose repeated cold start dominates direct execution or IPC; compare short-lived execution with measured idle lifetimes, retained memory, cleanup, crash recovery, and protocol migration cost |
| Incremental or reference-backed snapshots | A measured serialization or copy cost for a large accepted provider snapshot; keep the current small complete replacement until that cost appears |
| Project environment transactions | A reproducible conflict, partial transition, duplicated process, or latency problem that direct `direnv` and `mise` adapters do not solve |
| ZLE presentation composition | A concrete autosuggestion, highlighting, selection, search, diagnostic, or modal-editing conflict that current Zsh highlight layers cannot express |
| Structured history adapter | A lifecycle conflict or duplicated hook that an Atuin adapter can remove without `wsh` taking over its database or synchronization |
| Directory navigation adapter | Measured duplicated `chpwd` work or a widget conflict that a direct zoxide integration cannot solve |
| Command discovery and correction | A measured latency or correctness problem in an operating-system command-not-found provider, with execution remaining explicit |
| Long-command notifications | A concrete missed or duplicate notification case showing that shared lifecycle events improve on terminal or shell configuration alone |
| Remote and container adapters | A reproducible local-versus-remote path or lifecycle failure with an explicit mapping owner |
| Capability advertisement | A terminal-version heuristic that produces an incorrect behavior and is fixed by a small additive hint |
| Automatic terminal compatibility repair | Reproduced cases where a doctor's component-level recommendation is consistently correct across affected and unaffected versions; retain passive advice until automatic mutation has a clear safety benefit |
| Transient prompt coordination | A reproducible scrollback-density or redraw problem that cannot be solved by one theme-local Zsh hook while preserving OSC command zones |
| Structured command result metadata | A consumer that needs bounded exit status, duration, directory, or project records and cannot obtain them from lifecycle traces or an Atuin adapter without duplicated hooks |
| Enhanced keyboard integration | A Wakterm and ZLE input ambiguity reproducer that existing Kitty keyboard support does not already solve |
| Shell cloning | A specific state-restoration workflow whose benefit outweighs the ambiguity and security cost of transferring more than cwd and pane-history ancestry |

Mature utilities remain authoritative for their domains. [Atuin](https://docs.atuin.sh/) owns structured history and synchronization, [zoxide](https://zoxide.net/) owns directory ranking, and project environment managers own trust and tool selection. `wsh` can replace duplicated shell hooks when evidence supports it, but it should not absorb their databases, ranking algorithms, or policy.

## Evidence-driven sequence

1. Finish the Git-state provider, trusted prompt-component boundary, non-executable theme schema, benchmark comparison, immutable full-bundle layout, and signed reproducible update and rollback contract.
2. Add enough profiling and tracing to attribute the same workload across exact builds, then use it for later gates.
3. Run the foreground-startup counterfactual and add no `wsh` interface if the Wakterm-local fix passes.
4. Measure Wakterm's current lifecycle integration and test whether `wsh` phases let Wakterm remove it.
5. Persist a logical Wakterm pane token and test bounded and private history across restoration and process exit.
6. Benchmark static, direct dynamic, and Wakterm-mux completion paths with cancellation and resource limits.
7. Reduce pane metadata to fields demonstrated by Wakterm UI behavior.
8. Prototype terminal diagnosis only against recorded lifecycle failures and reproduced compatibility rules.
9. Investigate another candidate only after recording its baseline reproducer and expected consumer result.

## Boundaries remain explicit

- Wakterm owns layout, panes, terminal scrollback, viewport restoration, remote-domain path mapping, focus, visibility, and terminal input encoding.
- Applications own command models, provider state, percentage progress, executable selection, and application restoration.
- Zsh and ZLE own shell language semantics, command parsing, job control, and line editing. `wsh` does not replace them.
- `wsh` owns only accepted shell lifecycle integration, history policy, foreground coordination, state-provider behavior, and measurement established by the evidence gates above.
- A logical pane token is not an agent identity, provider identity, route, admission target, or security authority.
- Arbitrary command-output capture, process checkpointing, automatic command execution, a generic filesystem index, and a separate daemon for every state domain remain out of scope.
