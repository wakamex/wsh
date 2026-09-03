# Runtime coprocess startup no longer prints an internal job

The corrected integration reaches its Git-aware prompt without printing `[N] PID`, keeps the runtime outside the shell's process group, survives Ctrl-C at the prompt, restores interactive job control, and remains within every existing cold-start gate. The failure and fix were exercised under a real interactive bundled Zsh PTY, then the published `v0.1.1` bundle and corrected clean-revision bundle were each measured with 40 retained samples per startup path.

Zsh prints an asynchronous job announcement when `coproc` runs in an interactive shell with `MONITOR` enabled. `_wsh_runtime_start` disables `MONITOR` inside its existing local option scope before it creates the runtime coprocess, and `wsh-runtime serve` calls `setpgid(0, 0)` before loading the theme or reporting ready. The caller returns with `MONITOR=on`; the runtime becomes leader of a separate process group; and wsh retains the runtime PID, pipe descriptors, disown behavior, crash fallback, and shell-exit cleanup.

## Correctness result

The public `v0.1.1` transcript reproduced `[4] 849773` before the first prompt. Disabling `MONITOR` only around `coproc` hid the line but placed the runtime in the shell process group, so that counterfactual was rejected. The complete canonical bundle suite built clean revision `9a35f26c4586bee3420bc8f28476aeaa286c30e8` in the glibc 2.28 environment and passed runtime readiness, asynchronous Git rendering, internal-job suppression, distinct process-group checks from `/proc`, `MONITOR=on` restoration, a real Ctrl-C at the prompt, unchanged-state repaint suppression, crash fallback, normal shell-exit cleanup, relocation, and imported-symbol checks.

## Cold-start regression result

| Bundle and path | Median | p90 | Maximum |
|---|---:|---:|---:|
| Published v0.1.1 raw bundled Zsh | 5.054 ms | 5.793 ms | 6.406 ms |
| Published v0.1.1 direct complete integration | 7.243 ms | 7.976 ms | 9.486 ms |
| Published v0.1.1 managed complete startup | 8.076 ms | 9.443 ms | 10.883 ms |
| Corrected raw bundled Zsh | 4.968 ms | 5.119 ms | 5.453 ms |
| Corrected direct complete integration | 7.142 ms | 7.313 ms | 7.416 ms |
| Corrected managed complete startup | 7.806 ms | 7.987 ms | 8.870 ms |

| Fixed gate | Corrected result | Status |
|---|---:|---:|
| Managed p90 added over raw at most 5.0 ms | 2.867 ms | Pass |
| Managed maximum added over raw at most 8.0 ms | 3.417 ms | Pass |
| Manager p90 added over direct complete at most 1.0 ms | 0.674 ms | Pass |

The first safe-implementation run on CPU 0 passed the complete-startup gates but measured 1.172 ms of manager contribution at p90 and failed the 1.0 ms launcher gate. Host load was 4.47 and another process was consuming 128 percent CPU. The preregistered confirmation pinned both bundles to CPU 31, reversed their order by measuring the correction first, and passed all gates. The failed samples remain in [`fixed-cpu0-failed.tsv`](fixed-cpu0-failed.tsv), with the preceding published control in [`release-cpu0.tsv`](release-cpu0.tsv).

The corrected bundle's raw Zsh binary is byte-identical to the published control. The result supports absence of a material startup regression at the fixed product gates; it does not attribute the small between-run timing differences to the process-group changes.

## Reproduction

[`release.tsv`](release.tsv) and [`fixed.tsv`](fixed.tsv) contain the raw samples. [`metadata.txt`](metadata.txt) records the source revisions, bundle and executable identities, build configuration, host, workload, commands, and input hashes. The fixed hypothesis, thresholds, and attempt limit are in [`../runtime-job-announcement-plan-2026-09-03.md`](../runtime-job-announcement-plan-2026-09-03.md).
