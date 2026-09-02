# Tracing and retained memory pass fixed phase-one gates

The glibc 2.28 development bundle passes the new tracing-overhead and retained-memory gates. Tracing added 1.533 ms at runtime-ready p90 against a 3.0 ms limit and 0.190 ms at refresh p90 against a 0.5 ms limit. The combined Zsh and runtime path added 1,961 KiB of retained PSS at p90 and 1,981 KiB at maximum, below the fixed 4,096 KiB and 5,120 KiB limits.

The tracing comparison paired fresh traced and untraced runtimes for every sample, alternated pair order, and used the real parser, Git provider, renderer, trace writer, and 1,000-file fixture. The memory comparison paired fresh raw-Zsh and complete-wsh sessions, alternated pair order, warmed 20 prompts, waited 250 ms without input, and read Linux proportional set size from `/proc/PID/smaps_rollup`.

| Gate | Required | Observed | Result |
| --- | ---: | ---: | --- |
| Traced runtime-ready p90 overhead | At most 3.000 ms | 1.533 ms | Pass |
| Traced refresh p90 overhead | At most 0.500 ms | 0.190 ms | Pass |
| Added retained PSS p90 | At most 4,096 KiB | 1,961 KiB | Pass |
| Added retained PSS maximum | At most 5,120 KiB | 1,981 KiB | Pass |

## Paired tracing isolates trace work from Git variability

Each traced or untraced runtime launched through the same shell function, reached ready, warmed both sides of one state transition, returned to the preparation state, and then executed the timed transition. The ready comparison includes trace-file validation, creation, permission enforcement, and the first trace event. The refresh comparison includes the real protocol request, Git worker, renderer, snapshot response, and trace events; subtracting its paired untraced observation removes most shared provider cost. Nearest-rank p90 is calculated over 60 ready pairs and separately over 20 refresh pairs in each state, with the largest state p90 serving as the gate.

| State | Median refresh overhead | P90 refresh overhead | Maximum refresh overhead |
| --- | ---: | ---: | ---: |
| Clean | -0.007 ms | 0.149 ms | 0.355 ms |
| Dirty | -0.024 ms | 0.187 ms | 0.220 ms |
| Untracked | -0.010 ms | 0.190 ms | 0.318 ms |

Negative paired differences are retained rather than clamped because scheduler and provider variation can make the traced member faster. The gate uses the largest p90, not the most favorable state or median.

## The rejected PTY comparison exposed cold-state contamination

The first design ran complete PTY targets in forward and reverse order. Its traced-first block reported a 12.846 ms clean p90 followed by 7.165 ms dirty and 7.420 ms untracked p90s. A trace-only repetition reproduced a 12.053 ms clean p90 followed by normal later states. These runs passed calibration and correctness, but comparing separate targets could not distinguish trace work from cold repository and filesystem state.

The first paired runtime attempt still warmed only the preparation side of each state transition. Its clean scans stepped from roughly 9 ms to 4 ms during the run in both modes; one pair straddled that step, and the resulting 0.502 ms p90 missed the unchanged 0.500 ms gate by 0.002 ms. The accepted harness warms both sides before timing. The rejected [`trace-forward/`](trace-forward/), [`trace-reverse/`](trace-reverse/), [`trace-first-repeat/`](trace-first-repeat/), and [`trace-one-sided-warmup.tsv`](trace-one-sided-warmup.tsv) evidence is retained rather than attributed to a runtime regression.

## Added retained memory is about 2 MiB per session

The memory workload starts 20 fresh pairs. Raw mode measures the exact bundled Zsh after an editable prompt and 20 prompt cycles. Wsh mode measures the sum of that Zsh process and its runtime after the same workload, requires the runtime to have no live child after the quiet interval, and subtracts the paired raw result. Alternating order prevents every raw or wsh observation from receiving the same launch-order advantage.

| Measurement | Median | P90 | Maximum |
| --- | ---: | ---: | ---: |
| Raw Zsh PSS | 1,380 KiB | 1,392 KiB | 1,395 KiB |
| Wsh Zsh PSS | 1,844 KiB | 1,856 KiB | 1,860 KiB |
| Wsh runtime PSS | 1,483 KiB | 1,493 KiB | 1,515 KiB |
| Combined wsh PSS | 3,324 KiB | 3,339 KiB | 3,354 KiB |
| Added PSS over raw Zsh | 1,943 KiB | 1,961 KiB | 1,981 KiB |

PSS apportions shared pages among the processes mapping them, so these values describe this host and workload rather than a universal byte count. The gate fixes the same host-shaped workload for release comparisons and limits the per-session addition that compounds across many panes.

## Exact identities and commands

The wsh source revision was `0889d4519697613dc6f09eb8ad74b11d99344cc6`. The clean development bundle manifest digest was `23c167c70c9d7d677055043fccd543771d4829b22d7245fe2079263b53a1e083`, and its canonical archive SHA-256 was `09fac21b3a9a11561596f535405a46f35b67e6dd6b226431b179887ebf2c0fc0`. The Zsh SHA-256 was `bac80fcae8e1dd2aa1d5b77d5a68a7bb73612f8bf349d1f33e775117b7cd5cfb`, the runtime SHA-256 was `4fa59ffc191c59db064dad44f47534cf47ac08da6f35e1710935fd0f39477918`, and the integration SHA-256 was `2fc5fd142bd28d98f0a71c01f59be565fbade54b231c1d5c8d6afc4480d19f76`.

The accepted commands were:

```sh
WSH_TRACE_RUNTIME="$bundle/bin/wsh-runtime" WSH_TRACE_THEME=benchmarks/wsh-benchmark.toml WSH_TRACE_ITERATIONS=20 ./benchmarks/benchmark-trace-overhead.zsh > benchmarks/resource-gates-2026-09-02/trace.tsv
WSH_MEMORY_ZSH="$bundle/bin/zsh" WSH_MEMORY_RUNTIME="$bundle/bin/wsh-runtime" WSH_MEMORY_INTEGRATION="$bundle/share/wsh/integration.zsh" WSH_MEMORY_THEME=benchmarks/wsh-benchmark.toml WSH_MEMORY_BUNDLE_ROOT="$bundle" WSH_MEMORY_ITERATIONS=20 WSH_MEMORY_WARMUP_PROMPTS=20 ./benchmarks/benchmark-runtime-memory.zsh > benchmarks/resource-gates-2026-09-02/memory.tsv
./benchmarks/check-resource-gates.zsh benchmarks/resource-gates-2026-09-02/memory.tsv benchmarks/resource-gates-2026-09-02/trace.tsv > benchmarks/resource-gates-2026-09-02/gates.tsv
```

[`metadata.txt`](metadata.txt) records the runner and data digests, fixture, host, bundle, and workload identities. [`trace.tsv`](trace.tsv), [`memory.tsv`](memory.tsv), and [`gates.tsv`](gates.tsv) retain every accepted observation and the machine-evaluated result. The host ran Fedora Linux 44 with kernel 7.1.9-200.fc44.x86_64 on an AMD Ryzen 9 3950X with 32 online logical CPUs.
