# Cold compinit and first native completion dominate first-Tab time

Deferred completion spends roughly 159 ms in native initialization when the completion dump is absent, followed by about 65 ms in the first native Git completion. With a reusable dump, initialization falls to about 19 ms, while first native completion remains about 65 ms. Autosuggestion rebinding adds about 10 ms. Nine real-ZLE correctness cases passed before 100 matched normal/instrumented pairs and a separate 100-pair identical-control comparison.

| First-use stage | Missing dump median | Missing dump p95 | Reusable dump median | Reusable dump p95 |
|---|---:|---:|---:|---:|
| Mark compinit for autoload | 0.018 ms | 0.021 ms | 0.018 ms | 0.021 ms |
| Native compinit, including its audit and cache handling | 158.805 ms | 165.311 ms | 18.937 ms | 19.751 ms |
| Register Wsh-owned directory jumping | 0.089 ms | 0.104 ms | 0.086 ms | 0.101 ms |
| Restore the Tab delegate while retaining the directory-jump wrapper | 0.614 ms | 0.668 ms | 0.568 ms | 0.625 ms |
| Rebind Wsh-owned autosuggestion widgets | 10.385 ms | 11.194 ms | 10.078 ms | 10.494 ms |
| Invoke native expand-or-complete for the first Git branch | 64.954 ms | 67.365 ms | 64.706 ms | 67.110 ms |
| Complete timed initializer | 234.859 ms | 243.842 ms | 94.348 ms | 97.261 ms |
| Remaining parent-observed interval outside that initializer | 9.992 ms | 10.482 ms | 10.049 ms | 10.571 ms |

These are diagnostic spans. The fixed clock-overhead gate failed, and identical controls subsequently exceeded the same gate without any component clocks. The measurements support investigating the large stages, but do not establish sub-3 ms instrumentation accuracy. Each quantile is computed independently; stage quantiles must not be added together.

## First and second Tab remain different workloads

| Cache state and instrumentation | Shells | First Tab median | First Tab p95 | Second Tab median | Second Tab p95 |
|---|---:|---:|---:|---:|---:|
| Missing dump, unchanged prototype | 50 | 244.181 ms | 261.744 ms | 26.332 ms | 27.668 ms |
| Missing dump, buffered component clocks | 50 | 244.917 ms | 254.061 ms | 26.505 ms | 28.013 ms |
| Reusable dump, unchanged prototype | 50 | 103.997 ms | 109.726 ms | 26.318 ms | 27.528 ms |
| Reusable dump, buffered component clocks | 50 | 104.365 ms | 107.631 ms | 26.117 ms | 27.753 ms |

The uninstrumented results reproduce the earlier [first-Tab failure](../deferred-completion-2026-09-06/report.md) in both cache states. A fast second Tab cannot substitute for first-use latency. The roughly 65 ms native-completion stage includes everything beneath the completion widget, including any function loading, matching, and command work. This experiment does not split those mechanisms or count child processes.

## The paired p95 gate also fails without clocks

| Paired comparison | Pairs | Median first-Tab difference | p95 first-Tab difference | Relation to the fixed 3 ms gate |
|---|---:|---:|---:|---|
| Component clocks minus unchanged prototype, missing dump | 50 | 0.395 ms | 7.855 ms | Instrumentation gate fails |
| Component clocks minus unchanged prototype, reusable dump | 50 | -0.000 ms | 3.073 ms | Instrumentation gate fails |
| Identical control B minus A, missing dump | 50 | 0.407 ms | 6.274 ms | Exceeds 3 ms without clocks |
| Identical control B minus A, reusable dump | 50 | -0.445 ms | 5.679 ms | Exceeds 3 ms without clocks |

The initial [plan](plan.md) fixes the instrumentation gate and the 100-pair comparison. After that gate failed, the separate [variance plan](variance-plan.md) fixed another 100 pairs using byte-identical uninstrumented prototypes. Its result shows that a positive paired p95 difference is not specific evidence of clock overhead here. The instrumentation gate remains failed; neither its threshold nor its result was changed. Both matrices are retained, with no exclusions or retries.

## Buffered clocks and correctness

The [runner](run.py) imports the exact retained deferred-completion harness, verifies its hash, and reuses its private configuration, real Git repository, directory-jump database, PTY observer, and nine correctness cases. Both normal and instrumented fixtures preload `zsh/datetime` and define the same export widget. The instrumented copy inserts seven timestamp assignments around the six stages. It stores timestamps in memory and exports them only through a separate widget after the parent has measured the first and second Tab. There is no trace formatting or trace output inside the measured operation.

The [instrumented prototype](instrumented.zsh) retains the original native compinit invocation, audit, directory-jump ownership, delegate restoration, autosuggestion rebinding, and native completion. Correctness covers Git branches, spaced paths, directory-jump entries, repeated completion, history search, autosuggestion display and acceptance, highlighting, custom widgets, preexisting completion, a custom Tab binding, vi insert mode, and z as the first completion. Additional clock checks require exactly one initialization, seven ordered timestamps in timed cases, no timestamps in controls, and a complete internal interval within the parent-observed first-Tab time. Every measured shell returns the expected Git branch on both Tabs.

The parent retains decimal clock strings and subtracts them with decimal arithmetic before producing millisecond spans. Each span is nonnegative, and spans sum to the total interval. The remaining outer interval includes input processing before the initializer and work through the capture marker after it returns. It is not assigned to an unmeasured component.

## Workload identities and reproduction

All cases use the same manager binary built from `950bde517bdbb75d3c2a0933293b95f3d013a967` and unsigned development bundle `ccf3c17708aae1b1fc23c4170d54ff6e78a919f0adc0e0950f3590c6325c9698`, built from `2239f59bee65b0a083bfb291c15e17548012f828`. The [metadata](metadata.json) binds native binaries, the control and instrumented prototypes, both harnesses, fixture configuration, plan, target, and host. The complete bundle manifest retains pinned Zsh source and patches, toolchains, build profile, and payload identities. The bundle remains an unsigned local development artifact.

Both matrices use 50 rounds per cache state, reverse comparison and cache-state order on alternate rounds, and pin shell children to CPU 0. Missing-cache cases delete only `.zcompdump`; reusable-cache cases retain their earlier generated dump. Operating-system caches are not flushed. No local build, test, verification, or other tool-shell invocation overlaps either timing matrix. Correctness, first and second Tab observations, stage clocks, host observations, summaries, and 413 compressed PTY transcripts are retained.

With the exact native inputs available at the paths declared in the runner, use a fresh scratch directory and run `python3 benchmarks/completion-costs-2026-09-06/run.py correctness`, then `python3 benchmarks/completion-costs-2026-09-06/run.py measure`. The separately planned control comparison is `python3 benchmarks/completion-costs-2026-09-06/variance.py`. `python3 benchmarks/verify-completion-cost-evidence.py` checks the retained identities, transcripts, arithmetic, and gate outcomes without rerunning timing.

## Next experiment should split native initialization

Start with the roughly 159 ms missing-dump compinit stage. Its bundled source performs native audit, reads completion registration headers across fpath when no reusable dump is available, and writes a new compdump. Measure those operations separately before choosing an optimization. The roughly 65 ms first native completion is the next distinct target; separate function loading from candidate generation before proposing preloading or compiled functions. Autosuggestion rebinding is smaller, and directory-jump registration is negligible in this workload. No new cache, background initializer, or production behavior has been introduced.
