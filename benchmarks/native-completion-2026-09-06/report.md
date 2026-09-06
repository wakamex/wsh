# Eager native completion exceeds the startup budgets

An empty Wsh configuration lacks Git branch completion and completion for the built-in `z` command. Ordinary native `compinit` fixes both, but eager initialization adds 20.619 ms to cached startup p95 and 153.871 ms when the completion dump is missing. Both exceed the budgets fixed before testing. Actual ZLE correctness checks passed, followed by 50 runs per configuration using the same manager, bundle, and observer.

| Configuration | Shell starts | First-editable median | First-editable p95 | First Git branch completion p95 | Result |
|---|---:|---:|---:|---:|---|
| No completion initialization | 50 | 25.844 ms | 27.039 ms | Unavailable | Reproduces missing command-specific completion |
| Native `compinit`, missing completion dump | 50 | 170.353 ms | 180.910 ms | 76.008 ms | Startup exceeds the allowed 100 ms increase |
| Native `compinit`, reusable completion dump | 50 | 44.667 ms | 47.658 ms | 76.434 ms | Startup exceeds the allowed 20 ms increase |

The first-Tab budget of 100 ms passes in both initialized cases. Wsh's shipped behavior is unchanged. A subsequent experiment should test whether a small deferred initializer can preserve startup latency and user widget ownership without creating an excessive first-Tab delay. Moving the measured cold initialization onto Tab could exceed that interaction budget, so deferral needs its own evidence before implementation is accepted.

## Workload and fixed gates

The [plan](plan.md) fixes correctness, sample counts, ordering, budgets, and the one-hypothesis stopping rule. The [harness](run.py) creates private startup files and a small real Git repository, then runs the ordinary Wsh launcher through a PTY. Wsh's three editing defaults and directory jumping stay enabled; `WSH_THEME` is empty. The only configuration difference is `autoload -Uz compinit; compinit -i -d "$HOME/.zcompdump"`. The bundled native audit remains active; no `-C` or `-u` shortcut is used.

Correctness checks capture the actual editor buffer after Tab for a unique Git branch, a directory-jump database entry containing a space, and a filesystem path containing spaces. The baseline completes the filesystem path but leaves the Git and `z` prefixes unresolved. Both initialized variants complete all three. The [results](correctness.json) and compressed transcripts retain the actual buffers. This screens native initialization; an eventual integration still needs ownership and adversarial tests.

The measurement runs 50 rounds, alternating baseline/cold/warm and warm/cold/baseline order. Cold means the `.zcompdump` is absent, with operating-system page caches left intact. Warm means an earlier correctness run generated the dump. Startup ends at native OSC 133 `B`, after line-init. Completion timing includes submitting the short line and Tab, then receiving the capture widget's buffer marker. No profiling or process tracing is enabled, and no other local build, test, verification, or tool-shell invocation overlaps the timing run. Quantiles use the nearest-rank rule, with no exclusions or retries. The [samples](samples.json), [summary](summary.json), [host observations](host.json), and [measurement log](measurement.log) retain every result.

## Exact build and reproduction

The manager is the release build from `950bde517bdbb75d3c2a0933293b95f3d013a967`. All cases use unsigned development bundle `ccf3c17708aae1b1fc23c4170d54ff6e78a919f0adc0e0950f3590c6325c9698`, built from `2239f59bee65b0a083bfb291c15e17548012f828`, which already contains both v0.3.1 correctness fixes. This is a local development artifact. The [metadata](metadata.json) records manager, native binary, runtime, fixture configuration, harness, and plan hashes. The complete original bundle manifest retains the target, pinned Zsh revision and patches, toolchains, build profile, and payload digests. The observer and child run on the recorded host; only the child is pinned to CPU 0.

To reproduce, build or retain those exact inputs, copy `run.py` and `plan.md` into a fresh private scratch directory, and run `python3 /path/to/scratch/run.py correctness`, followed by `python3 /path/to/scratch/run.py measure`. The harness declares the exact manager and bundle paths at its top. Run without concurrent local work. Preserve both passing and failing outputs. `python3 benchmarks/verify-native-completion-evidence.py` checks the retained hashes, buffers, sample counts, quantiles, and failed gates without rerunning timings.
