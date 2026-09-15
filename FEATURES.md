# Wsh feature priorities

Wsh supplies a tested Zsh distribution with built-in editing features, directory jumping, optional asynchronous prompts, diagnostics and profiling. Native startup, the C component owners and system-package distribution are selected. Completed architecture decisions and their evidence live in [DESIGN.md](DESIGN.md); this document records remaining work and the evidence required to expand scope.

## Ordered priorities

Prioritize reliable daily use and easier installation. Complete the immediate work below before expanding the feature set; later items retain their stated dependencies and experiment gates.

| Priority | Work | User benefit and next gate |
| --- | --- | --- |
| 1 | Improve setup without OMZ | Persistent history now defaults on with live sharing off, while preserving explicit user settings. Complete fresh-configuration checks for completion, bindings and prompts. Add concise setup guidance and doctor findings for demonstrated gaps, preserving existing configuration and users who alternate between Zsh and Wsh. Automatic completion initialization remains subject to a separate passing experiment. |
| 2 | Add pane-local history | Make history useful within a restored terminal workflow. Wakterm must first persist a stable logical pane token. Test the smallest `fc -p` integration across mux restart before considering bounded Wsh-managed history. Keep shell history local and terminal scrollback in Wakterm. Private-history work must prove sentinel commands stay out of configured durable sinks and diagnostics after normal and interrupted exit. |
| 3 | Qualify another installation target | Let additional users install Wsh through their usual package tools. Select one distribution or architecture from actual user demand, then qualify its build, package transactions and login lifecycle independently. Fedora x86-64 remains the supported installation target. |
| 4 | Compare Wakterm completion paths | Test whether application completion can become smaller or faster without losing behavior. Recapture the application inputs, then compare current and pruned static completion with direct application completion. Consider the existing mux only if those paths leave a measured problem. Preserve candidate correctness, cancellation, deadlines and fallback; a generic broker needs a second demonstrated consumer. |

## Ongoing maintenance

| Work | Required practice |
| --- | --- |
| Upstream Zsh updates | Evaluate newer upstream changes, refresh the pinned source deliberately and rerun upstream, compatibility and package checks. Keep local fixes and potential upstream submissions current in [upstream bug records](UPSTREAM-ZSH-BUGS.md). |
| Upstream plugin changes | Review changes reported by the daily monitor and incorporate relevant behavior promptly. Preserve component-specific handoff behavior, settings and customizations. [Component compatibility](VENDORED-COMPONENTS.md) records support and possible feature lag. |
| Compatibility and release regressions | Treat reproduced startup, editing, completion, prompt, restore and login failures as maintenance priorities. Test real consumers alongside local component contracts. Existing package and shell correctness gates remain required for releases. |
| COPR updates | Publish explicitly selected, CI-qualified source commits and test signed-repository transactions before advertising packaging changes. Keep supported chroots and installation guidance current. |
| Package resource transitions | Define and test compatibility or an explicit restart policy before changing autoload-function compatibility, external-module ABI or helper protocol. The current layout change has a documented [session restart boundary](packaging/FEDORA-REVIEW.md#upgrade-boundary). |

## Settled decisions

Wakterm now restores applications through `wsh --run --login -- PROGRAM ARG...`; the fix is pushed and deployed. Its real-Wsh PTY regression covers exact argument bytes, suspension, resumption, Ctrl-C and normal exit status.

Native startup, system-package updates, the C component owners and one prompt helper per shell are selected. The legacy Rust crates and toolchain are retired. Compatibility with the earlier wrapper-based releases is outside the native release scope. The source RPM passes offline Fedora rebuild, packaging and login qualification. Published canonical artifacts use GitHub provenance. The Fedora 44 x86-64 [COPR channel](https://copr.fedorainfracloud.org/coprs/wakamex/wsh/) provides signed packages and ordinary DNF updates, with [repository qualification](benchmarks/copr-2026-09-13/report.md). Official Fedora inclusion remains a separate package-review process.

The older [migration inventory](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-qualification-2026-09-09/inventory-report.md) retains decisions that were open at its recorded revision. Its component-adoption, legacy-retirement and distribution-contract questions have since been resolved by [architecture qualification](DESIGN.md), [package qualification](benchmarks/fedora-packaging-2026-09-13/report.md) and the [release contract](RELEASES.md).

## Admission and experiment limits

A candidate becomes an accepted `wsh` feature only after its investigation records:

1. A runnable baseline reproducer against the current implementation.
2. An observable correctness failure or a measured cost such as latency, process count, repeated parsing, installed size, or retained memory.
3. The cheapest counterfactual that could solve the problem in its current owner without adding a `wsh` abstraction.
4. A `wsh` intervention only when it produces a proportionate measured improvement over the counterfactual for a concrete consumer.
5. A concrete consumer result such as deleted integration code, corrected restore behavior, fewer processes, lower latency, or a smaller generated artifact.
6. A regression test that compares the accepted path with the original baseline.

Source size is a useful discovery signal and deletion can be a concrete maintenance result, but line count by itself does not prove a performance or correctness problem. A new daemon, database, protocol, or compatibility layer requires evidence that a smaller adapter cannot provide the same result.

Profiling and tracing are accepted enabling capabilities because every admission gate depends on attributable measurements. They do not justify another feature by themselves. A profile must identify the build, workload, enabled components, external processes, provider work, prompt transitions, repaints, and terminal events while excluding command text and secrets by default. The same workload is measured with the same instrumentation mode before and after an intervention, and instrumentation overhead is measured separately.

Architectural simplification can justify an experiment when it removes demonstrated duplication, dependencies or compatibility glue, even when the current path meets its speed gate. Count the complete resulting implementation, including adapters, generated code and dependencies. A passing compatibility experiment with no worthwhile optimization supports retaining the existing owner.

Before implementation, fix a runnable baseline, the smallest counterfactual, correctness and resource gates, and an attempt/time budget. Run correctness and sanitizer checks where applicable before matched timing comparisons. After two failed interventions at one gate, audit the premise and require a new hypothesis. A new subsystem needs a concrete consumer benefit that simpler owner-local changes cannot provide. Follow [DEVELOPMENT.md](DEVELOPMENT.md) for retained identities and verification.

## Deferred candidates and admission triggers

| Candidate | Evidence required before design work |
|---|---|
| Automatic completion initialization | Native compinit registration scanning is adopted. Automatic/deferred initialization and installation dump seeds remain unselected. Require a new hypothesis that passes startup, first-Tab and stale/unusable-cache fallback gates while preserving user initialization and security checks. [Completion experiments](COMPLETION.md) retain the outcomes |
| Further parser consolidation | A reproduced correctness problem or a measured maintenance or runtime cost in the remaining Zsh adapters, predicates or optional highlighters. Compare the complete replacement and compatibility burden with a smaller fix in the current owner |
| Terminal diagnosis and metadata | Reproduced terminal-query, OSC or restore failures. Prefer deterministic advice over repair. Publish allowlisted metadata only when it eliminates measured terminal-side work or fills a concrete UI gap; exclude full commands |
| Contributed theme directory | A real submission workflow to exercise. Local selection and validation already work. Preserve open submission and mechanical admission for bounded, non-executable definitions, with curated recommendations separate. Design publisher identity, immutable version/digest mapping and update trust when that workflow exists |
| Lazy provider registration | A second provider whose eager parsing or startup has measurable cost; the counterfactual is conventional Zsh autoloading without a registry service |
| Resident provider idle expiration | A provider whose repeated cold start dominates direct execution or IPC; compare short-lived execution with measured idle lifetimes, retained memory, cleanup, crash recovery, and protocol migration cost |
| Git-state sharing across shells | Multiple Wsh shells must first demonstrate material duplicate Git work or aggregate memory cost. Compare same-repository and different-repository panes against the current per-session runtimes, measuring total memory, Git executions, CPU, and prompt freshness. Test simpler per-session request coalescing and caching before a per-user Git service; keep rendering and shell lifecycle local. Any shared prototype must preserve repository and worktree identity, relevant per-shell Git environment, invalidation after external changes, cancellation, mixed-version compatibility, disconnect cleanup, and usable prompts after service failure. Sharing the entire runtime remains deferred without separate evidence |
| Incremental or reference-backed snapshots | A measured serialization or copy cost for a large accepted provider snapshot; keep the current small complete replacement until that cost appears |
| Project environment transactions | A reproducible conflict, partial transition, duplicated process, or latency problem that direct `direnv` and `mise` adapters do not solve |
| General ZLE presentation composition | A concrete autosuggestion, highlighting, selection, search, diagnostic, or modal-editing conflict that the three accepted defaults and current Zsh highlight layers cannot express |
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

Reopen runtime embedding only for a measured need large enough to justify coordinating child ownership with Zsh. The [previous comparison](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-runtime-boundary-2026-09-09/report.md) selected the per-shell helper. Keep rendering and shell lifecycle local in any future collection-sharing experiment.

## Ownership boundaries

- Wakterm owns layout, panes, terminal scrollback, viewport restoration, remote-domain path mapping, focus, visibility, and terminal input encoding.
- Applications own command models, provider state, percentage progress, executable selection, and application restoration.
- Zsh and ZLE own shell language semantics, command parsing, job control, and line editing. `wsh` does not replace them.
- Native Zsh owns standard shell lifecycle reporting. `wsh` owns the selected source fix, exact first-job adapter, history policy, state-provider behavior, and measurements established by the evidence gates above.
- A logical pane token is not an agent identity, provider identity, route, admission target, or security authority.
- Arbitrary command-output capture, process checkpointing, automatic command execution, a generic filesystem index, and a separate daemon for every state domain remain out of scope.
