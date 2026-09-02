# Phase-one Git service passed its fixed correctness and latency gates

The first complete local wsh path passed its fixed correctness, process, lock, repaint, first-editable, updated-state p90, and updated-state maximum gates with both the minimal benchmark renderer and the Wakamex presentation. The matched benchmark used the exact bundled Zsh 5.9.2 binary, one 1,000-file fixture, and 20 clean, tracked-dirty, and untracked transitions per target, followed by staged and detached-HEAD checks.

| Gate | Required | Minimal renderer result | Wakamex renderer result |
| --- | ---: | ---: | ---: |
| Advertised semantics | 100 percent | 62/62 | 62/62 |
| First-editable maximum added over raw | At most 2.0 ms | 0.943 ms | 0.702 ms |
| Updated-state p90 added over raw | At most 7.1 ms | 6.893 ms | 6.608 ms |
| Updated-state maximum added over raw | At most 8.0 ms | 7.241 ms | 6.825 ms |
| Git processes per transition | At most 1 | 1 | 1 |
| Git processes without `GIT_OPTIONAL_LOCKS=0` | 0 | 0 | 0 |
| Repaints for a changed result | At most 1 | 1 | 1 |
| Repaints for an unchanged result | 0 | 0 in the PTY regression | 0 in the same adapter regression |
| New runtime processes per transition | 0 | 0 | 0 |

The minimal renderer's settled p90 was 7.377 ms clean, 7.296 ms dirty, and 7.337 ms untracked. Its corresponding raw p90 was 0.484 ms, 0.455 ms, and 0.462 ms. The result passes the fixed milestone gate but not the separate 5 ms added-latency stretch target.

The resident runtime by itself added at most 0.008 ms to corresponding p90 results and 0.032 ms to corresponding maxima. Enabling the bounded JSONL trace added at most 0.157 ms to a corresponding settled median and produced no positive settled p90 difference in this run. After one request, runtime PSS was 1,499 KiB; after 100 completed refreshes it was 1,523 KiB, a 24 KiB increase. The memory measurement establishes a baseline rather than a release threshold.

## The polling counterfactual recovered 0.785 ms at p90

The first clean-revision run missed the p90 gate at 7.678 ms added over raw. The Git worker used a 1 ms `try_wait` polling interval. Reducing only that interval to 100 microseconds lowered the worst added p90 to 6.893 ms and the worst added maximum from 7.673 ms to 7.241 ms. The failed run, raw samples, host telemetry, and hypothesis are retained in [`phase-one-pre-polling.md`](phase-one-pre-polling.md).

An earlier run is separately excluded because unrelated CPU pressure began only during the untraced wsh target: load rose from 0.90 to 6.64 and CPU pressure accumulated about 1.61 seconds, producing 57-121 ms outliers. Its samples and telemetry remain under the `phase-one-rejected-pressure-*` names. Every accepted-run phase boundary reported a 0.00 CPU-pressure `avg10`, and load declined from 1.38 to 0.90.

## The Wakamex definition reused the same provider

The second run changed only the theme definition and target semantics. It used the same runtime binary and one-process provider, passed all 62 applicable checks, and stayed inside the same fixed gates. Unit and PTY fixtures also cover changed-only cwd and repository presentation, compact clean state, main-branch hiding, detached tags, staged, modified, untracked, ahead, behind, diverged and operation markers, duration formatting, clear reset, hostile prompt values, and linked worktrees.

## Compatibility and lifecycle checks

The complete development bundle ran in the pinned Ubuntu 22.04 builder at the glibc 2.35 floor. Its automated floor suite passed 21 Rust tests, the upstream Zsh suite on the fresh source build, manifest and dynamic-library comparison, manager verification, a real provider request, theme validation, unchanged-repaint suppression, runtime-crash fallback, shell-exit cleanup, and a maximum required symbol check of `GLIBC_2.35`.

Runtime and manager tests cover malformed and oversized protocol input, stale and cancelled generations, process-group cleanup, linked-worktree common refs and annotated tags, diverged upstream state, all advertised operation markers, theme-schema rejection, prompt escaping, private bounded tracing, manifest tampering, entrypoint substitution, symlinks, interrupted activation state, and offline rollback from a broken active bundle.

## Identities and retained data

The provider source revision was `429140efb69ddefc78ebb361f04419895355f41f`. The development bundle manifest digest was `2304c8bd9d41ee9a1ca40bbfc334ecdc66a4b92301e2ce3919e65336dfe00a02`, the Zsh binary SHA-256 was `a6ca35036d4d05ee44c770c74411636c4f8b7ba665bb4887145ea33d8859af24`, and the runtime SHA-256 was `5d6e8847420178b32e92e35a6ab32ba501f1baf6e976c496abd5881219858856`. The benchmark revision was `8dc0b5fea25671d6745a556bffb740d3866e189c`, and its runner SHA-256 was `352c096f011eb282f12e6d4c12281340fac96b635a2879cc065d7637a6592872`.

The minimal-theme evidence is retained in [`phase-one-matched-samples-2026-09-02.tsv`](phase-one-matched-samples-2026-09-02.tsv), [`phase-one-matched-distribution-2026-09-02.tsv`](phase-one-matched-distribution-2026-09-02.tsv), [`phase-one-matched-target-summary-2026-09-02.tsv`](phase-one-matched-target-summary-2026-09-02.tsv), and [`phase-one-matched-telemetry-2026-09-02.tsv`](phase-one-matched-telemetry-2026-09-02.tsv). The Wakamex evidence uses the corresponding `wakamex-port-*` files. [`phase-one-runtime-memory-2026-09-02.tsv`](phase-one-runtime-memory-2026-09-02.tsv) records the separate 100-refresh memory run.

These are local development-bundle results. They do not satisfy the two-build reproducibility, GitHub attestation, immutable GitHub Release, updater-verification, or publication gates in [`../RELEASES.md`](../RELEASES.md).
