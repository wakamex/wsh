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

## Built-in prompts compared with OMZ

Wsh's Agnoster prompt accepted input in about 3 ms versus 45–56 ms for OMZ Agnoster. Robbyrussell accepted input in about 3 ms versus 4 ms, with fresh Git status arriving about 9 ms sooner in Wsh. The comparison ran both prompt implementations on the same native Wsh binary, loading the same archived OMZ framework and preserving its default async policy. Each theme, repository size and Git state used 50 alternating pairs with normal CPU affinity. [Full report and retained evidence](https://github.com/wakamex/zsh-theme-bench/blob/e67ca009a4145eef02dc3def5afa59a1523d3b75/research/wsh-comparison-2026-09-12/report.md).

| Theme | Tracked files | OMZ input-ready median (ms) | Wsh input-ready median (ms) | OMZ fresh-Git median (ms) | Wsh fresh-Git median (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Robbyrussell | 1,000 | 3.84 | 3.00 | 16.33 | 7.24 |
| Robbyrussell | 10,000 | 3.99 | 3.13 | 23.48 | 14.69 |
| Agnoster | 1,000 | 44.61 | 3.03 | 44.53 | 7.79 |
| Agnoster | 10,000 | 56.18 | 3.06 | 56.11 | 14.70 |

These rows show clean repositories; modified, staged and untracked cases support the same interpretation. Readiness measures no-op submission to native OSC 133 B. Freshness measures the new branch becoming visible, followed by validation of the complete rendered state. Fixture mutations and Git checks occur before timing, so these are warm-filesystem prompt-return results. OMZ Robbyrussell already updates asynchronously; its readiness reduction was only 0.79–0.88 ms, below the experiment's 1 ms headline threshold. Separate probes found one Git invocation per Wsh update versus five for OMZ Robbyrussell and sixteen for OMZ Agnoster.

A retained single-CPU counterfactual exaggerated Robbyrussell's readiness advantage to 3.7–4.0 ms; the figures above use normal affinity. These are complete prompt-implementation comparisons with different presentation features, rather than an isolated measurement of C rendering or a claim about arbitrary Zsh themes. Both runs passed state checks and observer calibration; the detailed report retains every sample, configuration and source/binary identity.

## C helper compared with Rust

The complete helper comparison reduced executable size from 1,679,240 bytes to 372,320 bytes, about 78%, and active collection used two helper threads instead of three. Correctness comparisons covered protocol decoding, rendered prompt bytes, real Git repositories, cancellation and lifecycle behavior. The selected helper keeps one process per shell. See the [complete helper comparison](benchmarks/native-render-2026-09-08/runtime-report.md) and its [installed selection](benchmarks/native-qualification-2026-09-09/runtime-report.md).

This comparison establishes a smaller helper and passing latency gates. It does not establish a general speed advantage over Rust: the largest paired p95 collection increase was 0.207 ms, and startup increases were 0.314 ms with the existing prompt and 0.419 ms with Minimal. The isolated Git collector and renderer ports likewise passed their gates without establishing a useful latency improvement. Scheduling and ownership changed alongside the implementation language.

## Interpretation

The plugin comparisons use 50 alternating pairs per workload and measure complete editor or command paths, rather than only inner C functions. Their baselines are interpreted Zsh implementations. The helper comparison uses the earlier Rust helper with matching native shell and integration resources. These are separate component experiments at the linked revisions, not a single final-release-versus-old-release benchmark; their gains must not be added together.

The C consolidation also removed the Rust manager/runtime crates and the Cargo/rustc build dependency. Build-tool migration has no measured build-time speedup claim. Its benefits are fewer build dependencies and a shared native installation inventory; see the [guarded build qualification](benchmarks/native-consolidation-2026-09-10/build-report.md). Zsh still owns the language and editor, and selected configuration, lifecycle and optional-highlighter adapters remain Zsh code.
