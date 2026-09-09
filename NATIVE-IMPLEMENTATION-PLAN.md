# Native Wsh implementation and testing plan

Wsh will use a native entrypoint in its patched Zsh, expose its tools through one user-facing executable, and use system packages for installation and updates. An all-C implementation is the preferred hypothesis for the remaining functionality. The implementation work below tests whether each transition reduces responsibilities, interfaces, dependencies, or compatibility special cases while preserving user behavior. Existing Rust code, shell adapters, plugins, theme formats, and helper processes provide comparison baselines and can be replaced.

This plan records the decisions agreed on 2026-09-08. The [native-entrypoint experiment](benchmarks/native-entrypoint-2026-09-08/report.md) is complete; execution status and completed evidence are tracked in [NATIVE-PROGRESS.md](NATIVE-PROGRESS.md). Production still uses the current launcher and distribution workflow. This document defines the selected destination and execution order; [ARCHITECTURE-EVIDENCE.md](ARCHITECTURE-EVIDENCE.md) records the supporting experiments and [DEVELOPMENT.md](DEVELOPMENT.md) defines evidence and release checks.

## Selected architecture and open implementation choices

| Selected decision | Implementation freedom |
|---|---|
| Native Wsh entrypoint owns startup and Wsh tool invocation | Implement directly in C; use the existing prototype as a starting point and simplify it where comparisons support deletion |
| Zsh retains language, native shell arguments, startup-file semantics, job control, and ZLE | Add Wsh behavior at the owning native boundary while preserving those contracts |
| Shell startup works without per-user activation state | Choose a coherent system installation layout; user configuration and caches remain optional inputs to basic shell availability |
| One user-facing `wsh` executable provides diagnostics, profiling, version reporting, and exact foreground startup | Select explicit Wsh options without treating ordinary script names as manager subcommands; private implementation helpers remain possible |
| System packages own installation and updates | Start with a Fedora RPM vertical slice, then validate each additional supported package target; package ownership replaces self-update for those installations |
| Prompt rendering and shell lifecycle stay local to each shell | Keep the tested per-shell helper after the [native child-ownership comparison](benchmarks/native-runtime-boundary-2026-09-09/report.md); reopen embedding only for a measured requirement that justifies its coordination cost |
| All C is the preferred implementation hypothesis | Prototype and compare each substantial replacement; retaining Rust requires a concrete comparative reason, and a C port must pass its behavior and resource gates |

The current theme syntax, plugin implementations, runtime protocol, allocation patterns, and release bundle layout are revisable. Compatibility changes need an explicit migration and tests. Non-executable theme definitions, safe rendering of repository data, and the advertised Zsh configuration behavior remain product requirements. A new shell language or replacement for ZLE is outside this plan.

## Common implementation and acceptance procedure

Each stage begins with one runnable baseline, its exact identities, a bounded candidate, the smallest counterfactual, and a recorded hypothesis. For architectural simplification, the observed cost can be duplicated startup semantics, an unnecessary process or language interface, dependencies, or code required solely to bridge implementations. A current implementation does not need to fail a speed test before a simplification prototype is allowed.

Before coding, fix the stage's correctness assertions, workloads, statistics, sample counts, quantitative gates, and attempt/time budget. Preserve existing gates for comparable workloads. The native startup experiment supplies a +3 ms paired p95 regression gate; completion retains its 100 ms first-Tab budget. Different workloads need their own declared gates rather than borrowed measurements. After two failed interventions at the same gate, audit the premise and record a new hypothesis before another change. These bounds apply to experiments, rather than imposing an arbitrary deadline on the whole migration.

Run correctness and adversarial checks before timing. C changes receive compiler diagnostics, AddressSanitizer and UndefinedBehaviorSanitizer checks where supported, and focused fuzzing for newly implemented parsers or message readers. Keep sanitized runs separate from release-build timing. Prefer existing upstream components or libraries when they reduce total implementation burden; compare their dependencies and contracts rather than adopting them solely because they are conventional.

Count the complete resulting implementation: C and Rust code, remaining Zsh glue, generated code, interfaces, helper binaries, dependencies, build rules, and migration code. Identify which old code can actually be deleted. Performance parity can pass an architectural change that measurably simplifies ownership; a smaller diff alone does not establish a simpler system.

Retain input source, exact commands, effective configuration, patches, compiler settings, native and helper identities, raw results, failures, and computed summaries. Compare matched workloads and instrumentation, measure instrumentation overhead separately, and use native editor readiness rather than visible prompt text. Add accepted evidence verifiers to `benchmarks/verify-retained-evidence.zsh`. Commit independent causal changes separately after relevant checks and `git diff --check`; run the complete retained-evidence suite before pushing. Release authorization and exact-commit CI gates remain in force.

## Ordered stages

| Order | Deliverable | Decision or capability established |
|---|---|---|
| 1 | Native command interface, detailed version reporting, and doctor | One complete native tool slice and a concrete C maintenance comparison |
| 2 | Production native startup and exact foreground invocation | Remove the shell launcher and manual user-file loading from ordinary startup |
| 3 | System-package installation and login vertical slice | Prove default-shell availability independently of user activation data |
| 4 | Native profiling and report generation | Attribute subsequent changes without a standalone Rust manager dependency |
| 5 | C Git collector behind the existing process interface | Compare implementation language while holding architecture fixed |
| 6 | C theme parsing and rendering | Complete a comparable C prompt runtime and reassess the theme implementation |
| 7 | Helper-process versus in-process runtime experiment | Choose the simpler asynchronous runtime boundary using the same C functionality |
| 8 | Completion initialization and first-use improvements | Resolve the demonstrated standalone completion gap |
| 9 | Native interactive components, one at a time | Choose implementations for directory jumping, history search, autosuggestions, and highlighting |
| 10 | Migration cleanup and release qualification | Remove superseded implementations and deliver the accepted native system package |

This is the default order. Stages 5 through 9 are separately admitted replacements, not prerequisites for releasing a tested native shell after the core installation and tool work. A failed or inconclusive experiment records its result and leaves its baseline usable. Shared Git collection across shells remains separately deferred.

### 1. Native command interface, detailed version reporting, and doctor

Define the public syntax before wiring every feature to it. Prototype explicit options for doctor, profiling, detailed version information, and exact foreground invocation. Names such as `--wsh-doctor` are candidates, not a settled interface. Native `-c`, `-l`, `-i`, `-s`, `-f`, ordinary script arguments, and `--` keep their Zsh meanings. Record how existing `wsh doctor`, `wsh profile`, `wsh version`, and `wsh -- <argv>` callers migrate.

Implement detailed version reporting first, followed by doctor, directly in C. Version reporting must provide useful executable identity without user state; optional installed metadata can add provenance and component identities. Doctor must inspect the same effective configuration and deterministic plugin/theme ownership cases as today, without editing files or unloading user hooks. Compare a direct native implementation with the existing Rust commands; temporary delegation may support development but counts as retained glue.

Test argument boundaries, script names that resemble tool commands, malformed and non-UTF-8 arguments, exit codes, missing metadata, mismatched component identities, and no-active-state operation. Reuse doctor fixtures for exact duplicates, modified and unknown plugins, disabled components, and real OMZ prompt overlap. Verify unchanged startup files and ordinary shell invocation. Record native code, dependencies, interfaces, command latency, and deletion opportunities.

Completion condition: the public interface is specified, native version and doctor behavior pass, and the resulting comparison explains whether the C approach simplifies the tool implementation. No separate public `wshctl` is introduced as the target interface.

### 2. Production native startup and exact foreground invocation

Integrate the accepted startup experiment into the normal build and source lock. Remove manual user-file sourcing and the ZDOTDIR/RCS restoration state machine. Resolve installed resources before consumers need them, keep the user's prompt choice local, and preserve explicit terminal-policy settings. Remove transitional manager metadata only when its consumers have migrated.

Implement the foreground interface selected in stage 1 while keeping one native Zsh as the job-table owner. Forward exact argument bytes without rebuilding shell source. Evaluate whether a native startup action can replace the current one-shot shell callback; keep the implementation that provides the clearest ownership with fewer special cases.

Run direct execve and PTY tests for native login argv[0], shell flags, scripts, redirected and unset ZDOTDIR, global and user startup files, startup evaluation context, initial status, RCS/GLOBAL_RCS suppression, and login/logout order. Exercise missing and unusable user state, early module loading, relocated resources, disabled integration, and nested shells. Foreground tests must cover exact argv, foreground process groups, Ctrl-C including applications that consume it, Ctrl-Z, `fg`, repeated launches, terminal restoration, hooks, and OSC marker counts. Use the corrected primary-prompt observer from the prototype so a continuation prompt cannot satisfy a completion wait.

Completion condition: the native path passes upstream and Wsh contracts, including actual OMZ coexistence, and matched readiness measurements pass the fixed regression gate. Ordinary startup executes the native shell directly without the Rust launcher. Management code still used elsewhere does not count as deleted.

### 3. System-package installation and login vertical slice

Build a local RPM containing the complete native installation, initially with any still-required baseline runtime. Choose a stable account-shell path, root-owned executable and resources, package-controlled registration in `/etc/shells`, and installation-relative resource lookup. Basic shell availability must not depend on HOME, XDG locations, caches, activation JSON, or a working optional prompt service.

Define upgrade and removal behavior using the package manager's real mechanisms. Test coherent executable/module/helper selection, including a running shell that loads a module or starts its optional runtime after an upgrade. Choose a layout that keeps those resources compatible for their required lifetime. Determine how unavailable optional components degrade to a usable native shell, and distinguish missing required executables or libraries from recoverable integration failures. Avoid introducing a second updater or mutable activation authority for the system installation.

Use a disposable headless VM for package transactions and account tests. Start genuinely distinct unprivileged accounts with empty homes; test missing, corrupt, inaccessible, and incompatible user state, differing login and terminal environments, account-home availability, package permissions, and enforcing SELinux. Exercise PAM/TTY login and the graphical-login shell invocation relevant to the Fedora incident, then reboot and verify access through automation. Record whether a complete display-manager login was exercised or only its invocation boundary. Keep an independent recovery account or access path in the test VM; do not change the live host's account shell.

Test fresh installation, upgrade, failed/interrupted transactions, package-manager downgrade where supported, coexistence with system Zsh, and removal while an account still names Wsh as its shell. Select and document concrete removal behavior that avoids silently leaving accounts pointed at a missing shell; validate it against the package manager rather than assuming a scriptlet can prevent removal in every mode.

Completion condition: a real packaged native shell starts for fresh accounts without Wsh setup and survives the tested update/reboot workflows. Document remaining unrecoverable installation failures accurately. The existing per-user installer remains available until stage 10 supplies a migration.

### 4. Native profiling and reporting

Move profile invocation, lifecycle instrumentation, trace handling, and report generation behind the native interface. Compare a direct C implementation with the existing Rust reporter and Zsh instrumentation. Use native startup boundaries to remove trace-only shell interception where possible. Preserve optional function profiling through Zsh's established facilities and recovery of reports after interrupted sessions.

Test known injected startup and editor delays, component attribution, exact command status, empty module fallback paths, truncated and malformed traces, interrupted writes, schema/version handling, and report recovery. Verify that default output excludes command text, secrets, environment contents, and sensitive paths. Keep trace formatting and output off the measured path. Repeat existing matched startup and runtime instrumentation gates using the same statistics and workloads; retain failed runs.

Completion condition: native invocation and reporting pass attribution, privacy, recovery, and overhead gates. Remove the old reporter only after its supported consumers and saved-report behavior have a tested replacement or explicit migration. Subsequent port measurements use this accepted measurement boundary.

### 5. C Git collector with the process boundary held fixed

Port one complete Git request/cancellation/snapshot path to C while retaining the same per-shell helper-process boundary and consumer interface. This isolates the language decision. Compare the current Rust implementation, the C implementation, and any small simplification available without a port. Record total code and dependencies, including libraries used for parsing and process management.

Run the existing repository-state matrix and adversarial inputs: clean, modified, untracked, detached, operation states, worktrees, unusual path bytes, repository changes during collection, slow or failed Git, cancellation storms, stale generations, malformed output, child death, and shell exit. Preserve optional-lock behavior, complete snapshots, bounded resources, and process cleanup. Sanitizer and parser-fuzz cases precede performance comparisons.

Measure warm and cold collection, CPU, retained memory, process counts, cancellation responsiveness, and editor readiness. Completion condition: the C path passes semantics and fixed resource gates and gives a documented simplification or other concrete advantage. Keep the process architecture unchanged until the language comparison is complete.

### 6. C theme parsing and rendering

Port theme validation and rendering against the accepted collector interface. First establish parity for shipped themes and existing definitions. Then separately compare format or renderer simplifications; changing language and definition format in one experiment would hide their individual effects. The existing schema and rendering implementation are replaceable if their replacements improve the complete design.

Test every shipped presentation, invalid definitions, unknown fields, size limits, control characters, hostile repository strings, prompt escapes, malformed encodings, and rendering of long values. Verify that definitions cannot execute shell code or inject arbitrary terminal controls. Compare theme load time, render and repaint cost, code, dependencies, and installed size. Reuse the real terminal parser where emitted sequences change.

Completion condition: a C runtime can provide the selected themes and Git behavior under the existing process architecture, with tested migration for any format changes. Preserve local prompt ownership and unchanged user configuration. Retire corresponding Rust modules only when their consumers have moved.

### 7. Helper-process versus in-process asynchronous runtime

Using the same accepted C collector and renderer, compare the per-shell helper with integration into Zsh's native event handling. Measure the existing cost of IPC, serialization, process lifetime, and duplication before designing new machinery. The C helper supplies the simplest counterfactual; the same collector can also be simplified without moving it into the shell.

Test slow and hung Git, large results, rapid directory changes, typing during refresh, command cancellation, Ctrl-C/Ctrl-Z, repaint coalescing, runtime failure, shell exit, nested shells, and independent panes. In-process work must keep blocking subprocess waits and unbounded parsing away from editor callbacks. Compare cleanup code, state machines, copied data, total memory/CPU, idle resources, startup, editing latency, and prompt freshness. Record the failure-containment difference explicitly.

Completion condition: select the simpler passing process architecture and delete superseded IPC or supervision only where the chosen path removes its need. Prompt rendering and shell lifecycle remain local in either case. A helper process is an implementation option, rather than a permanent requirement.

### 8. Completion initialization and first-use improvements

Resume the demonstrated first-Tab investigation using the accepted profiling path. Separate compinit audit, registration scanning, dump generation, function loading, and candidate generation. Test smaller cache, compilation, or initialization changes before a replacement completion subsystem. Native C changes are available wherever measurements show they simplify or accelerate the owning operation.

Measure startup, first Tab, and subsequent Tab with missing, reusable, stale, and unusable dumps. Keep the established first-Tab budget and native security checks; moving work from startup to Tab does not erase its cost. Test Git branches, spaced paths, directory jumping, custom widgets and bindings, vi mode, existing compinit, plugins, correctness of candidates, cancellation, bounds, and fallback.

Completion condition: accept a path that passes both startup and first-use gates with existing completion compatibility. Treat Wakterm's static/direct/mux completion comparison as a distinct application-facing experiment described in [COMPLETION.md](COMPLETION.md), rather than a prerequisite for shell completion initialization.

### 9. Native interactive components, one at a time

Compare the existing component, its smallest configuration or adapter improvement, and a focused native C implementation. The initial order below increases editor interaction and composition complexity; revise it only when retained profiling identifies a more valuable target.

| Order | Component | Required behavior and measurements |
|---|---|---|
| 9a | Directory jumping | Ranking and persistence behavior, existing data, spaces and hostile paths, custom commands, completion, hook counts, lookup latency, and write cost |
| 9b | History substring search | Navigation semantics, keymaps and custom bindings, cursor/buffer state, multiline entries, history size, latency, and composition |
| 9c | Autosuggestions | Suggestion selection, cancellation, acceptance, stale results, custom widgets, history changes, editing latency, and process work |
| 9d | Syntax highlighting | Supported syntax, styles, layered highlights, redraw behavior, multiline input, large buffers, plugin composition, latency, and allocations |

Use the existing upstream implementations as behavioral references and existing real-ZLE fixtures as regression coverage. Add independent cases where a self-authored test might merely repeat the candidate's assumptions. Replacing a plugin implementation must preserve documented configuration behavior or provide an explicit migration. Test exact duplicates, modified and unknown plugins, and real OMZ coexistence for each change.

Completion condition for each component: choose the simpler passing implementation, retain evidence, and remove its obsolete code and dependencies. A result for one component does not authorize assuming the same result for the others. ZLE remains the editor throughout.

### 10. Migration cleanup and release qualification

Inventory all remaining Rust, shell, C, packaging, and compatibility responsibilities after the selected stages. Remove the Rust toolchain and dependencies only if no retained component needs them. Remove the standalone manager's update/activation responsibilities from the system-package path, and remove obsolete startup files, environment variables, helper protocols, and documentation after their callers have migrated. Count the final installed and maintained implementation again, including retained compatibility paths.

Implement migration from the per-user installation without deleting user configuration, history, themes, or the only working account shell. Define PATH precedence between an old launcher and the new system executable, the treatment of old activation records, and how existing commands report or redirect to their replacements. Update Wakterm's exact-foreground invocation and verify it with its real caller/parser. Document package-based update and recovery commands for each supported target.

Run upstream tests, complete Wsh correctness and hostile-input suites, real-configuration matrices, sanitizers, package install/upgrade/downgrade/removal tests, distinct-account login/reboot checks, and resource gates on the final tree. Run the canonical glibc 2.28 validation and independent two-build comparison; any proposed target-floor or artifact-contract change needs its own recorded decision and replacement coverage. Validate package metadata and transactions with the actual package tools, and compare normalized payloads and package artifacts under a declared reproducibility contract.

Update release, provenance, installation, security, and user documentation together with their implementation. Preserve the existing exact-commit eligibility check and explicit release authorization until an approved workflow change replaces them. No package publication or account-shell change is implied by writing or executing local prototype stages.

Completion condition: the released package contains the selected native implementation, all shipped paths pass their applicable gates, obsolete user-facing commands have a tested migration, and users can select the system shell without creating a dependency on private activation state.

## Deferred cross-shell collection experiment

Cross-shell Git sharing is not a prerequisite for any stage above. Reopen it only when same-repository and different-repository pane workloads show material duplicate Git work or aggregate memory cost. Compare per-session coalescing and caching before a per-user collection service. Any shared candidate needs repository/worktree and environment identity, external-change invalidation, cancellation, version coexistence, reconnect/cleanup behavior, and usable local prompts after service failure. Keep rendering and shell lifecycle local. The admission trigger remains in [FEATURES.md](FEATURES.md).
