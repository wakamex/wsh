# End-to-end profiling attributes Wsh startup within the fixed overhead gates

`wsh profile` can now identify where time is spent from manager launch through the first editable prompt and the initial asynchronous Git repaint. The accepted run added 2.251 ms at first-editable p90 against an otherwise identical normal Wsh session. The isolated runtime trace added 1.688 ms at readiness p90 and 0.458 ms at refresh p90. All three fixed gates passed.

The test used the complete development bundle, the normal manager entrypoint, a PTY, and a 1,000-file Git repository. It paired normal and profiled shells in both orders for 100 observations per variant, then used the established isolated runtime workload to separate trace cost from Git and PTY variance.

## Accepted results

| Gate | Required | Observed | Result |
|---|---:|---:|---|
| Default profile first-editable p90 overhead | At most 3.000 ms | 2.251 ms | Pass |
| Runtime-ready p90 trace overhead | At most 3.000 ms | 1.688 ms | Pass |
| Runtime refresh p90 trace overhead | At most 0.500 ms | 0.458 ms | Pass |

| End-to-end metric | Variant | Samples | Median | p90 | Maximum |
|---|---|---:|---:|---:|---:|
| First editable | Normal | 100 | 27.808 ms | 29.012 ms | 31.419 ms |
| First editable | Profile | 100 | 29.565 ms | 30.321 ms | 35.845 ms |
| Settled Git prompt | Normal | 100 | 37.425 ms | 38.892 ms | 42.003 ms |
| Settled Git prompt | Profile | 100 | 39.663 ms | 40.814 ms | 46.542 ms |
| Paired first-editable overhead | Profile minus normal | 100 pairs | 1.755 ms | 2.251 ms | 5.056 ms |
| Paired refresh overhead diagnostic | Profile minus normal | 100 pairs | 0.412 ms | 0.724 ms | 1.029 ms |

The end-to-end settled difference remains a diagnostic because it includes independent Git-process scheduling and two PTY reads. The fixed refresh gate uses the paired runtime benchmark, which warms both states and isolates trace recording around the same provider, parser, renderer, and response path. Its highest state-level refresh p90 overhead was 0.458 ms.

Optional `--functions` mode loads Zsh's native `zprof`, so it is a separate instrumented workload rather than the default profile. Across 40 pairs, its first-editable overhead was 2.277 ms median and 3.633 ms p90. It is intended for attribution after the default spans identify a Zsh-owned region and is not governed by the default profile's 3 ms gate.

## Correctness and privacy

The packaged PTY fixture starts a profiled interactive shell through the active-bundle state, loads user `.zshenv` and `.zshrc`, reaches the initial Git prompt, produces a useful report while the shell is still live, exits, and reproduces the report from the retained directory. It verifies bundle and Zsh identity, built-in ownership, theme, startup spans, repository discovery, one Git child process, parsing, rendering, response writing, snapshot publication, and repaint application.

The same fixture places sentinel values in user startup files and verifies that the trace contains neither those values nor the repository path. It rejects command, prompt, and cwd fields, requires mode 0700 session storage and mode 0600 files, checks the 8 MiB trace and 1 MiB function-profile bounds, and rejects an incomplete JSON event. A normal `wsh` launch creates no additional profile directory.

The same complete suite passed in the canonical glibc 2.28 builder. That build produced bundle `ab5b836e03e5c6c5588bae4a68eb0f178c31887021c2be5d5e81ffd15b6719f9`, imported no glibc symbol newer than 2.28, and retained archive SHA-256 `5dfdc91a31da7902a4a92629d9484016a1729219932aa874e135929c091fd790`.

## Accepted design

The manager creates one private session, records the bundle digest and a cross-process time origin, and then replaces itself through the normal shell launch path. Thin Zsh probes bracket the standard startup filenames, Wsh defaults, integration startup, `precmd`, and first ZLE readiness. The existing runtime trace adds repository discovery, Git process, parsing, child count, rendering, response-write, publication, and cancellation measurements.

Startup events remain in memory until the first editor is ready. Later Zsh events and runtime events are flushed only after measured prompt work finishes or the runtime becomes idle. The report runs after shell exit, or explicitly through `wsh profile report <profile-directory>` for a live or interrupted session. Default traces contain identifiers and durations rather than commands, prompt contents, provider values, environments, or paths.

## Rejected counterfactuals and run exclusions

Always enabling `zprof` changed ordinary profile cost, so function timing became explicit `--functions` mode. Repeated file-stat calls, pre-launch manifest parsing, per-event writes, trace encoding before worker launch, worker-event writes before response delivery, inline snapshot serialization before repaint, and sourcing the profile helper during ordinary startup each moved work onto a measured hot path and were rejected. The retained `failed-*` inputs show those iterations and the accepted implementation removes the corresponding work rather than loosening a gate.

One nominal final run was excluded after concurrent host work raised normal first-editable p90 from about 30 ms to 68 ms and produced 12.628 ms paired p90 overhead. Its raw samples are retained as `failed-host-load-samples.tsv`. The same command was rerun after the competing CPU job ended; no implementation or threshold changed.

## Reproduction

```sh
./build/build-development-bundle.zsh
./tests/profile.zsh target/release/wsh <bundle>
./benchmarks/benchmark-profile.zsh benchmarks/profile-2026-09-05/samples.tsv target/release/wsh <bundle> 50
./benchmarks/summarize-profile.zsh benchmarks/profile-2026-09-05/samples.tsv benchmarks/profile-2026-09-05/summary.tsv
WSH_PROFILE_BENCH_FUNCTIONS=1 ./benchmarks/benchmark-profile.zsh benchmarks/profile-2026-09-05/functions-samples.tsv target/release/wsh <bundle> 20
WSH_TRACE_RUNTIME=<bundle>/bin/wsh-runtime WSH_TRACE_THEME=benchmarks/wsh-benchmark.toml WSH_TRACE_ITERATIONS=20 ./benchmarks/benchmark-trace-overhead.zsh > benchmarks/profile-2026-09-05/runtime-trace.tsv
./benchmarks/check-profile-gates.zsh benchmarks/profile-2026-09-05/summary.tsv benchmarks/profile-2026-09-05/runtime-trace.tsv
./benchmarks/verify-profile-evidence.zsh
```

[`metadata.txt`](metadata.txt) records the exact source, bundle, binary, toolchain, host, workload, commands, and retained-file hashes. [`samples.tsv`](samples.tsv), [`functions-samples.tsv`](functions-samples.tsv), [`runtime-trace.tsv`](runtime-trace.tsv), and [`gates.tsv`](gates.tsv) retain the accepted observations and machine-evaluated result.
