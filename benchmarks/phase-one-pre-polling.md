# One-millisecond Git polling missed the phase-one p90 gate

The first clean-revision matched run passed semantic, process-count, optional-lock, repaint, first-editable, maximum-latency, idle-runtime, and trace-overhead checks, but the highest updated-state p90 added 7.678 ms over raw bundled Zsh and missed the fixed 7.1 ms gate. The result used 20 clean, tracked-dirty, and untracked transitions per target with the exact bundled Zsh 5.9.2 binary and one 1,000-file fixture.

| Gate | Short result |
| --- | ---: |
| Advertised semantics | 20/20 clean, dirty, and untracked plus staged and detached HEAD |
| First-editable maximum added over raw | 0.684 ms |
| Updated-state p90 added over raw | 7.678 ms, failed 7.1 ms gate |
| Updated-state maximum added over raw | 7.673 ms |
| Git processes per transition | 1 |
| Git processes without `GIT_OPTIONAL_LOCKS=0` | 0 |
| Repaints for each changed result | 1 |
| Idle-runtime first-prompt maximum added over raw | 0.031 ms |
| Highest traced p90 added over matching untraced p90 | 0.089 ms |

The untraced wsh p90 was 7.855 ms clean, 8.082 ms dirty, and 8.095 ms untracked. The corresponding raw p90 was 0.438 ms, 0.404 ms, and 0.459 ms. The maximum gate uses the maximum difference within each corresponding state rather than subtracting unrelated extrema.

The worker polls `try_wait` and sleeps 1 ms while Git is active. The direct-Git control settled at 5.421 ms, 5.361 ms, and 5.421 ms medians, while the complete path settled at 7.704 ms, 7.752 ms, and 7.969 ms. Reducing only that polling interval to 100 microseconds is the next counterfactual. If it does not pass the same clean-revision run, the next step is to profile the remaining runtime and adapter overhead rather than changing the gate.

## Identities and retained data

The wsh source revision was `f2ad55393ef560e6cdd39111a6deab03102cb2ae`. The development bundle manifest digest was `7bac49e80083e922a46495316ea95d7d7b85b2ef6ee16888da9adfc9870abb32`, the Zsh binary SHA-256 was `a6ca35036d4d05ee44c770c74411636c4f8b7ba665bb4887145ea33d8859af24`, and the runtime SHA-256 was `842524259bce7b86906f8a8cecb7b56dbe4493aaf15a2c0263a108a8168bb793`. The benchmark revision was `bb3d89e13a6354257e80443b2d85736862086fd6`, and the runner SHA-256 was `ea87ddbd979fc6be528bdf099a724bb5ca040c1c40bdb6eecd055df584c6530a`.

The raw samples are in [`phase-one-pre-polling-samples-2026-09-02.tsv`](phase-one-pre-polling-samples-2026-09-02.tsv), the generated distribution summary is in [`phase-one-pre-polling-summary-2026-09-02.tsv`](phase-one-pre-polling-summary-2026-09-02.tsv), and host telemetry is in [`phase-one-pre-polling-telemetry-2026-09-02.tsv`](phase-one-pre-polling-telemetry-2026-09-02.tsv). A preceding run interrupted by unrelated CPU pressure is retained separately under the `phase-one-rejected-pressure-*` names and is excluded from the gate.

## Reproducer

```sh
cd ../zsh-theme-bench
./research/benchmark-core-themes.zsh --iterations 20 --fixture-files 1000 --settle-ms 150 --target raw --target wsh-idle --target direct-git --target wsh --target wsh-trace --samples-output ../wsh/benchmarks/phase-one-pre-polling-samples-2026-09-02.tsv --telemetry-output ../wsh/benchmarks/phase-one-pre-polling-telemetry-2026-09-02.tsv --zsh ../wsh/build/portable/glibc-2.35/bundles/7bac49e80083e922a46495316ea95d7d7b85b2ef6ee16888da9adfc9870abb32/bin/zsh --wsh-integration ../wsh/build/portable/glibc-2.35/bundles/7bac49e80083e922a46495316ea95d7d7b85b2ef6ee16888da9adfc9870abb32/share/wsh/integration.zsh --wsh-runtime ../wsh/build/portable/glibc-2.35/bundles/7bac49e80083e922a46495316ea95d7d7b85b2ef6ee16888da9adfc9870abb32/bin/wsh-runtime --wsh-theme ../wsh/benchmarks/wsh-benchmark.toml
./research/summarize-core-theme-samples.zsh ../wsh/benchmarks/phase-one-pre-polling-samples-2026-09-02.tsv
```
