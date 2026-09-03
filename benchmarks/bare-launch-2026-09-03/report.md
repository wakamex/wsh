# Bare wsh reaches an editable prompt in 7.990 ms at p90

Invoking `wsh` without arguments now launches the active shell through the same dispatch path as `wsh run`. The glibc 2.28 build reached its first editable prompt in 7.990 ms at p90, adding 0.545 ms over direct complete integration and 2.939 ms over raw bundled Zsh. All existing startup gates passed.

The floor suite separately verified that both bare `wsh` and explicit `wsh run` replace the launcher process with the bundled Zsh. The complete Rust, relocated-bundle, provider, PTY lifecycle, and glibc 2.28 ABI checks also passed.

| Bundle and path | Median | p90 | Maximum |
|---|---:|---:|---:|
| Raw bundled Zsh | 4.935 ms | 5.051 ms | 5.162 ms |
| Direct complete integration | 7.276 ms | 7.445 ms | 7.759 ms |
| Bare wsh managed startup | 7.799 ms | 7.990 ms | 8.243 ms |

| Fixed gate | Result | Status |
|---|---:|---:|
| Managed p90 added over raw at most 5.0 ms | 2.939 ms | Pass |
| Managed maximum added over raw at most 8.0 ms | 3.080 ms | Pass |
| Manager p90 added over direct complete at most 1.0 ms | 0.545 ms | Pass |

## Implementation

CLI dispatch maps a genuinely empty argument list to the existing `run` match arm. Named subcommands retain their current parsing, `wsh run` remains available for explicit invocation, and Zsh arguments remain behind `wsh run --`. The empty dispatch adds no process, file read, network request, parser, or persistent state.

## Measurement method

The complete development bundle was built from source revision `2a7bda4447805757f49c4bb8448c5391290ae099` in the pinned Rocky Linux 8.10 glibc 2.28 builder. The benchmark used the existing 1,000-file Git fixture, five warmups per variant, 40 retained samples per path, alternating forward and reverse order, CPU 31 affinity, and the established Zsh `zpty` clock. Raw Zsh, direct complete integration, and bare managed startup used the same bundle and instrumentation.

[`startup.tsv`](startup.tsv) contains every retained sample. [`metadata.txt`](metadata.txt) records the exact source, bundle, binaries, toolchains, builder, workload, command, input hashes, host, and CPU. The behavior and unchanged performance gates were fixed before implementation in [`../bare-launch-plan-2026-09-03.md`](../bare-launch-plan-2026-09-03.md).
