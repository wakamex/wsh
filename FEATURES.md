# Wsh feature priorities

Wsh supplies a tested Zsh distribution with built-in editing features, directory jumping, optional asynchronous prompts, diagnostics and profiling. Native startup, the C component owners and system-package distribution are selected. Completed architecture decisions and their evidence live in [DESIGN.md](DESIGN.md); this document records remaining work and the evidence required to expand scope.

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

## Settled decisions

Native startup, system-package updates, the C component owners, one prompt helper per shell and fresh-installation release scope are selected. The legacy Rust crates and toolchain are retired. The source RPM is implemented and passes offline Fedora rebuild and login qualification. Published canonical artifacts use GitHub provenance; a separate maintainer RPM signature and hosted repository are not part of the current release contract.

The older [migration inventory](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-qualification-2026-09-09/inventory-report.md) retains decisions that were open at its recorded revision. Its component-adoption, legacy-retirement and distribution-contract questions have since been resolved by [architecture qualification](DESIGN.md), [source-RPM qualification](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/source-rpm-2026-09-11/report.md) and the [release contract](RELEASES.md). Historical decision tables are evidence, not the current backlog.

## Remaining work

| Work | Current decision and next gate |
| --- | --- |
| Native release | Installation and package qualification are complete for their recorded revisions. Choose an authorized version, prepare its committed notes and pass exact-candidate CI before publication. [RELEASE-REVIEW.md](RELEASE-REVIEW.md) tracks preparation; [RELEASES.md](RELEASES.md) defines authorization. |
| Distribution channel and additional targets | The Fedora source RPM is implemented and qualified. Choose whether to pursue a hosted repository such as COPR or downstream distro inclusion, and qualify that channel before advertising it. No repository or submission is configured. Fedora x86-64 remains the supported installation target; qualify each new distribution or architecture independently. This does not block the existing direct-RPM release path. |
| Standalone completion initialization | Native compinit registration scanning is adopted. Automatic/deferred initialization and installation dump seeds remain unselected. Reopen only with a new hypothesis that passes startup, first-Tab and stale/unusable-cache fallback gates while preserving user initialization and security checks. [COMPLETION.md](COMPLETION.md) retains outcomes. |
| Wakterm completion | Compare pruned static completion, direct application completion and the existing mux against freshly captured application inputs. Select the smallest passing path for installed size, cold/warm latency, candidate correctness, cancellation and fallback. A generic broker needs a second demonstrated consumer. |
| Pane history | Wakterm must persist a stable logical pane token first. Compare a small native `fc -p` integration with bounded Wsh-managed history across mux restart; keep shell history local and terminal scrollback in the terminal. Private-history work must test that sentinel commands never reach configured durable sinks or diagnostics after normal and interrupted exit. |
| Terminal diagnosis and metadata | Start from reproduced terminal-query, OSC or restore failures. Prefer deterministic advice over repair. Publish allowlisted metadata only when it eliminates measured terminal-side work or fills a concrete UI gap; exclude full commands. |
| Contributed theme directory | Local theme selection and validation are implemented. Reopen directory work when there is a submission workflow to exercise. Preserve open submission and mechanical admission for supported, bounded, non-executable definitions; separate admission from curated recommendations. Publisher identity, immutable version/digest mapping and update trust need a concrete design and tests at that point. No directory or automatic theme-update service exists today. |
| Upstream plugin changes | Catalog and bounded Git recognition are implemented, and the daily monitor reports changed upstream inputs for review. Incorporate relevant changes promptly while preserving component-specific handoff behavior. [Component compatibility](VENDORED-COMPONENTS.md) records support and possible feature lag. |

A release does not require pane history, a theme directory, shared Git collection, a generic completion broker or a new foreground-job protocol. The existing package and shell correctness gates remain required.

## Deferred candidates and admission triggers

| Candidate | Evidence required before design work |
|---|---|
| Incompatible package resources | A proposed release changes autoload-function compatibility, external-module ABI or helper protocol. Define and test compatibility or an explicit restart policy before that release; the current compatible package path does not need an additional recovery subsystem |
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
