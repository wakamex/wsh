# Git output stays cancellable after the direct child exits

The runtime now drains Git stdout in the worker's existing timeout and cancellation loop. A real-Git fixture with a descendant holding stdout open previously failed shutdown after 2.517 seconds and left that descendant alive. The corrected runtime cancels and shuts down in 1.187 ms, with the descendant gone. All six paired collection workloads, native readiness comparisons and retained resource gates pass.

| Collection workload, 1,000 tracked files, 50 alternating pairs | Baseline median | Corrected median | Paired p95 regression | Gate |
|---|---:|---:|---:|---|
| Clean repository, fresh helper after ready handshake | 9.004 ms | 8.928 ms | +0.289 ms | At most +3 ms, pass |
| Clean repository, reused helper | 8.726 ms | 8.642 ms | +0.222 ms | At most +3 ms, pass |
| 100 modified tracked files, fresh helper after ready handshake | 4.010 ms | 3.957 ms | +0.080 ms | At most +3 ms, pass |
| 100 modified tracked files, reused helper | 3.921 ms | 3.841 ms | +0.116 ms | At most +3 ms, pass |
| 100 untracked files, fresh helper after ready handshake | 4.236 ms | 4.183 ms | +0.117 ms | At most +3 ms, pass |
| 100 untracked files, reused helper | 4.125 ms | 4.117 ms | +0.200 ms | At most +3 ms, pass |

| Additional gate | Observed | Required |
|---|---:|---|
| Existing-prompt native first-editable regression, 50 pairs | +0.878 ms paired p95 | At most +3 ms, pass |
| Minimal native first-editable regression, 50 pairs | +1.108 ms paired p95 | At most +3 ms, pass |
| Runtime tracing readiness overhead, 60 pairs | 1.137 ms p90 | At most 3 ms, pass |
| Worst per-state runtime tracing refresh overhead, 20 pairs per state | 0.216 ms p90 | At most 0.5 ms, pass |
| Existing runtime/integration retained-memory workload, 20 pairs | 1,681 KiB added PSS p90; 1,701 KiB maximum | At most 4,096 / 5,120 KiB, pass |

## Correction and maintenance cost

The old worker waited for the direct Git process, then joined a separate blocking stdout-reader thread. Once the direct child had exited, that join no longer observed cancellation or the two-second deadline. A remaining writer could keep it blocked. The corrected worker reads a nonblocking pipe while continuing to check both process completion and stdout EOF, with the same 4 MiB output bound and two-second deadline. Every error path kills the Git process group and waits for its direct child.

This removes one thread and the worker/reader join boundary. The fault fixture observes four active runtime threads before the fix and three after it. The correction adds 25 net Rust lines, adds no dependency or helper process, and reduces the release runtime binary from 1,685,968 to 1,679,320 bytes. The per-shell helper, request protocol, snapshot parser and renderer remain unchanged. This is the accepted smaller counterfactual for the subsequent C collector comparison.

| Fresh-helper CPU time, including Git plus helper startup/shutdown, median of 50 samples | Baseline | Corrected |
|---|---:|---:|
| Clean fixture | 10.300 ms | 10.306 ms |
| Modified fixture | 5.375 ms | 5.350 ms |
| Untracked fixture | 5.611 ms | 5.563 ms |

## Correctness and retained methods

The workspace test suite passes, including real annotated-tag/worktree collection, cancellation process groups, stale generations and malformed protocol handling. The fresh native bundle passes all 75 upstream scripts with zero failures and two skips, nine Wsh integration suites, and the runtime PTY suite covering job control, Ctrl-C, unchanged repaint suppression, runtime-crash fallback and shell-exit cleanup.

The inherited-pipe regression uses actual Git output and adds only a descendant retaining stdout. It verifies descendant removal before harness cleanup, so cleanup cannot turn a leaked process into a passing result. A second case verifies that the two-second deadline still returns an error and leaves the runtime usable without an explicit cancel. Four further real-Git fault cases cover oversized output, invalid UTF-8, a nonzero exit, and a process that closes stdout before remaining alive. They require `GIT_OPTIONAL_LOCKS=0`, an error response, a subsequent ping, and successful shutdown. New C code or parser logic is not introduced by this Rust correction.

The [stage-5 plan](../native-git-2026-09-08/plan.md) fixes the counterfactual, workloads, thresholds and attempt budget. Measurements run sequentially on CPU 0 after correctness. Fresh-helper results measure the first collection after its ready handshake; they do not claim a globally cold filesystem cache. Reused helpers receive one warmup collection. Exact snapshots must match between implementations on every pair. Compare implementations within each fixture; the clean fixture is collected immediately after its initial commit, while the other fixtures follow reset and mutation.

The native startup control copies only the three unrelated compiled-path-dependent resource files from the candidate. Native source behavior is unchanged in this Rust fix; executable build identities and helper bytes are recorded separately. Memory uses the original raw-Zsh-5.9.2 versus runtime/integration workload, preserving its original gate; it is not a measurement of the entire native distribution. CPU measurements use sequential child resource accounting and include helper startup/shutdown outside the collection-latency interval.

[metadata.json](metadata.json), `inputs.tar.gz`, `results.tar.gz` and `manifest.json.gz` retain exact source, baseline source, tests, commands, toolchain/host/flags, native/helper identities, fixtures, failures, raw measurements and summaries. The shared verifier recomputes the paired and resource gates. The historical builtins/theme verifier now reads its original runtime source from the already pinned historical commit, preserving its original digest. All builds are unsigned local development artifacts. Canonical glibc-floor and final package qualification remain stage-10 work; no release or push was performed.
