# Native C performance results

Moving repeated plugin work into C reduced editing, highlighting, directory-command and cold-completion costs in the retained comparisons. The largest measured gains are in long highlighting inputs and large history/directory datasets. Each component was checked for correctness before alternating baseline/candidate timing runs; the reports below retain exact builds, fixtures and raw measurements.

| Measured workload | Baseline | Selected C implementation | Result and evidence |
| --- | ---: | ---: | --- |
| Main highlighting, short-command complete redraw median | 2.123 ms, original Zsh main highlighter | 1.378 ms | 35.1% reduction; [installed highlighting](benchmarks/native-highlighting-installed-2026-09-10/report.md) |
| Main highlighting, 100 repeated commands complete redraw median | 119.652 ms, original Zsh main highlighter | 11.203 ms | 90.6% reduction; the four tested workloads improve 35–91%; [installed highlighting](benchmarks/native-highlighting-installed-2026-09-10/report.md) |
| Autosuggestions, complete editing sequence with 10,000 history entries, median | 7.294 ms, pinned Zsh plugin | 5.160 ms | 29.3% reduction; [installed autosuggestions](benchmarks/native-autosuggestions-installed-2026-09-10/report.md) |
| History substring search, complete editing sequence with 10,000 entries, default mode, median | 11.032 ms, pinned Zsh plugin | 8.526 ms | 22.7% reduction; [installed history](benchmarks/native-adoption-2026-09-10/history/report.md) |
| History substring search, complete editing sequence with 10,000 entries, uniqueness enabled, median | 238.097 ms, pinned Zsh plugin | 65.840 ms | 72.3% reduction; [installed history](benchmarks/native-adoption-2026-09-10/history/report.md) |
| Directory lookup, complete command with 1,000 records, median | 52.542 ms, pinned Zsh owner | 8.540 ms | 83.7% reduction; [installed directory owner](benchmarks/native-directory-final-2026-09-10/installed-report.md) |
| Cold completion startup, p95 | 155.429 ms, original compinit registration | 123.600 ms | 31.829 ms reduction; warm startup stays approximately 37.6–37.8 ms; [installed completion](benchmarks/native-adoption-2026-09-10/completion/report.md) |
| First editable prompt after autosuggestion adoption, existing prompt, median | 22.558 ms, previous native installation | 15.989 ms | 6.569 ms reduction; Minimal improves by 6.626 ms; [installed autosuggestions](benchmarks/native-autosuggestions-installed-2026-09-10/report.md) |

## C helper compared with Rust

The complete helper comparison reduced executable size from 1,679,240 bytes to 372,320 bytes, about 78%, and active collection used two helper threads instead of three. Correctness comparisons covered protocol decoding, rendered prompt bytes, real Git repositories, cancellation and lifecycle behavior. The selected helper keeps one process per shell. See the [complete helper comparison](benchmarks/native-render-2026-09-08/runtime-report.md) and its [installed selection](benchmarks/native-qualification-2026-09-09/runtime-report.md).

This comparison establishes a smaller helper and passing latency gates. It does not establish a general speed advantage over Rust: the largest paired p95 collection increase was 0.207 ms, and startup increases were 0.314 ms with the existing prompt and 0.419 ms with Minimal. The isolated Git collector and renderer ports likewise passed their gates without establishing a useful latency improvement. Scheduling and ownership changed alongside the implementation language.

## Interpretation

The plugin comparisons use 50 alternating pairs per workload and measure complete editor or command paths, rather than only inner C functions. Their baselines are interpreted Zsh implementations. The helper comparison uses the earlier Rust helper with matching native shell and integration resources. These are separate component experiments at the linked revisions, not a single final-release-versus-old-release benchmark; their gains must not be added together.

The C consolidation also removed the Rust manager/runtime crates and the Cargo/rustc build dependency. Build-tool migration has no measured build-time speedup claim. Its benefits are fewer build dependencies and a shared native installation inventory; see the [guarded build qualification](benchmarks/native-consolidation-2026-09-10/build-report.md). Zsh still owns the language and editor, and selected configuration, lifecycle and optional-highlighter adapters remain Zsh code.
