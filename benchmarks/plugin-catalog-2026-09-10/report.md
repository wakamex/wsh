# Shared upstream recognition catalog

Wsh now recognizes 18 upstream snapshots through one provenance catalog while retaining each component's handoff rules. Every entry passes an automated host matrix, including native suggestions/history, modified implementations, initialized settings and lifecycle opt-ins. Startup adds 0.7-0.8 ms at the median with autosuggestions alone and 1.5-1.6 ms with all five plugins loaded. Both workloads pass the 3 ms paired-p95 gate over 50 alternating pairs per prompt mode.

| Startup workload | Prompt | Baseline median readiness | Catalog median readiness | Paired p95 added readiness | Gate |
|---|---|---:|---:|---:|---|
| Only upstream v0.7.0 autosuggestions | Existing | 18.847 ms | 19.533 ms | 1.139 ms | <= 3 ms, pass |
| Only upstream v0.7.0 autosuggestions | Wsh minimal | 19.573 ms | 20.346 ms | 1.171 ms | <= 3 ms, pass |
| All five recognized upstream plugins | Existing | 53.086 ms | 54.597 ms | 2.220 ms | <= 3 ms, pass |
| All five recognized upstream plugins | Wsh minimal | 31.595 ms | 33.195 ms | 2.102 ms | <= 3 ms, pass |

## Baseline and fixed gates

Baseline `3d63e23` repeats byte-comparison code across five adapters and recognizes only individually wired snapshots. Introduce one build-verified provenance catalog and shared bounded byte comparison while preserving each component's takeover boundary. Test every catalog snapshot through real startup, native behavior, settings preservation and modified-copy rejection before expanding admission. Existing component contracts, doctor and the glibc 2.28 component suite must pass. Startup paired p95 overhead must remain <= 3 ms across 50 alternating pairs per prompt mode against the baseline. Two failed interventions at a gate require a new hypothesis; older lifecycle families that fail the handoff remain deferred instead of growing compatibility machinery.

## Legacy binding-rule correction gate

The authentic v0.5.2 source excludes `zle-*` in its binder, rather than in its default ignore list. Losing that implicit rule during native takeover reproduces recursive wrapping of `zle-line-pre-redraw`. Adding the pattern to the inherited list restores display and acceptance. A proposed unconditional controller exclusion was rejected after upstream's changelog established that v0.6.0 deliberately made lifecycle widgets configurable. The selected correction makes the implicit exclusion explicit only for the v0.5.2 handoff family; newer versions retain lifecycle opt-ins. Native controller code remains unchanged. Require v0.5.2 editor behavior, explicit `zle-line-init` opt-in and custom `zle-` widgets on later versions, ten controller editor modes, lifecycle/bounds tests and the original startup gate. No upstream Zsh defect is claimed.

## Accepted coverage and fallback

| Component | Recognized upstream snapshots | Handoff |
|---|---|---|
| Autosuggestions | v0.5.2, v0.6.0, v0.6.1, v0.6.2, v0.6.3, v0.6.4, v0.7.0, v0.7.1 | Replace the pending implementation before widgets or asynchronous work become active. Preserve the pre-v0.6.0 implicit lifecycle exclusion; retain later lifecycle opt-ins. |
| History substring search | v1.0.0, v1.0.1, v1.0.2, v1.1.0, pinned 14c8d2e, OMZ 9112b53 | Remove owned highlighting hooks and load the current native adapter, preserving configured values at handoff. |
| Syntax highlighting | Pinned 2fc57d6 and older b2c910a | Replace main parsing while retaining supported external lifecycle and optional highlighters. |
| Directory jumping | OMZ 9112b53 | Preserve aliases, settings and lifecycle registration; replace query/persistence and recording functions. |
| Git-prompt | OMZ a7426f0 | Remove the recognized collector hooks only when Wsh owns the prompt. |

An uncataloged source remains external. File mismatch does not establish that the user customized it, so doctor calls it unverified and explains that it may be an unlisted upstream version or customized. No startup network lookup, version-string heuristic, user Git metadata dependency or executable plugin update is added.

`build/plugin-catalog.py` validates schema, file count, handoff family, immutable revision format, source boundaries, size and hashes before installing the table. Shared bounded in-process byte comparison replaces the duplicated adapter implementations. Multi-file matches must belong to one catalog entry. Runtime function provenance and active-state checks remain local to each adapter. Installed references are deduplicated by content hash and occupy 655,878 bytes including the catalog metadata/table in the measured installation. The source snapshots and their embedded licenses remain unchanged.

## Verification and reproduction

The 80-case matrix covers every admitted snapshot, source modifications, runtime implementation overrides and configured styles. Autosuggestion entries additionally cover active-copy preservation, explicit disable, displayed/accepted suggestions and, from v0.6.0 onward, lifecycle opt-in with a working custom `zle-` widget. History entries search actual history through ZLE. Component contracts retain broader highlighting, directory persistence, prompt ownership and editor-composition coverage. Separate bounds tests reject unknown components, wrong arity, missing/empty/oversized files and mixed-version pairs.

All nine host component contracts pass, along with the 80-case catalog matrix, 11 real OMZ autosuggestion cases, ten controller editor comparisons, cancellation/child reaping and oversized-response cleanup. The host builds pass 75 upstream Zsh scripts with zero failures and two skips. The actual personal `.zshrc` also passes native ownership and suggestion display/acceptance in Wsh while regular Zsh retains its external plugin; startup-file hashes remain unchanged. The selected native autosuggestion controller is byte-identical source to the baseline; the only native C change is doctor wording.

The complete canonical glibc 2.28 suite passes against a freshly built native executable, including all nine contracts, the same 80-case catalog matrix, installed highlighting, autosuggestions, recovery, profiling, completion, history, directory persistence and runtime lifecycle checks. RPM assembly and native release-format checks pass. The native floor build passes 75 upstream scripts with zero failures and two skips. This run rebuilds the native installation and RPM; it is not a component overlay. Sanitizers were not rerun for the unchanged controller and diagnostic-text-only C change.

Run `python3 build/plugin-catalog.py --check`, `python3 tests/plugin-catalog-inputs.py`, `zsh tests/plugin-recognition.zsh INSTALLATION` and `python3 native/test-plugin-catalog.py INSTALLATION OUTPUT`. The last two run automatically through `native/check-installation.py`, including canonical floor builds. Run `native/test-installed-autosuggestions.py INSTALLATION OUTPUT MODE` with each of `correctness`, `lifecycle` and `bounds` for the controller gates.

Run `python3 native/measure-older-autosuggestions.py BASELINE_INSTALLATION CANDIDATE_INSTALLATION OUTPUT` for the single-plugin fixture and `python3 native/measure-plugin-catalog.py BASELINE_INSTALLATION CANDIDATE_INSTALLATION OUTPUT` for all five. Timing uses CPU 0, tracing off, the same sources/configuration within each pair and native OSC 133 B after ZLE initialization. Samples alternate order; paired p95 uses sorted index 47 and the reported median uses index 24. Correctness precedes timing. These isolated workloads do not claim a speedup for the full personal configuration.

`identity.json` binds sources, manifests, Zsh locks, compiler/target, build commands and executable identities. `evidence.tar.gz` retains raw measurements, summaries, host/floor logs, the matrix and direct verification of all 21 file references against upstream Git objects. The initial recursion reproducer and successful ignore-pattern counterfactual are retained. All installations are unsigned development artifacts. No release, user installation or startup-file edit is performed. The dated [upstream activity review](upstream-review.md) distinguishes recent commits, stable tags and lifecycle changes.
