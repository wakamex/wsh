# Startup-order fixes pass the profiling overhead gate

Neither correctness fix produced a profiling-overhead failure in the matched experiment. All six runs passed the unchanged 3 ms p90 limit; the current code measured 2.281 and 2.283 ms. The comparison used identical launcher, runtime and Zsh binaries, 100 normal/profile pairs per run, and a fixed forward/reverse sequence with no concurrent validation work.

| Run | Source variant | Normal first-editable median | Profiled first-editable median | Paired profiling overhead p90, limit 3 ms | Gate |
|---|---|---:|---:|---:|---|
| 1 | v0.3.0 baseline | 29.564 ms | 31.494 ms | 2.376 ms | Pass |
| 2 | Module-path fix | 29.802 ms | 31.729 ms | 2.537 ms | Pass |
| 3 | Both startup-order fixes | 29.584 ms | 31.375 ms | 2.281 ms | Pass |
| 4 | Both startup-order fixes | 29.812 ms | 31.572 ms | 2.283 ms | Pass |
| 5 | Module-path fix | 29.752 ms | 31.682 ms | 2.326 ms | Pass |
| 6 | v0.3.0 baseline | 29.525 ms | 31.229 ms | 2.336 ms | Pass |

The profiling-overhead question left open by the two correctness commits is resolved for this workload. No production optimization, threshold change, or reversal of the fixes is warranted by these results.

## Earlier comparison had two confounders

The earlier failed candidate runs overlapped other validation work. Their prior-bundle control also contained a v0.2.0 runtime while the candidates contained v0.3.0. That control did not isolate the startup-order change. The earlier failures remain retained in ../profile-module-path-2026-09-06; this experiment does not establish the exact cause of each timing outlier.

## Matched inputs and correctness

The three clean detached source revisions are 2e2651f (v0.3.0), 2d69d55 (module-path fix), and 2239f59 (both fixes). Builds use the same pinned local Zsh build, toolchain and optimized Rust configuration. All three launcher, runtime and Zsh binary hashes match. The only differing payload file is share/wsh/zdotdir/.zshenv. Manifest source identities identify each variant independently. These are unsigned local development artifacts.

Each variant passed its own revision's real profile correctness test before timing. The baseline test predates the empty-module-path regression, which intentionally fails on baseline code; the corrected variants include it. No correctness tests, evidence verification, builds or diagnostic tracing ran concurrently with the measured sequence. Unrelated host services were left running.

## Measurement and verification

The unchanged benchmark uses an empty user configuration, the minimal theme, enabled built-in defaults, and a 1,000-file committed Git fixture. It observes native OSC 133 B after ZLE initialization. Each run warms up five times per mode, then retains 100 adjacent normal/profile pairs in forward and reverse mode order. The six source runs are baseline, module-path fix, both fixes, both fixes, module-path fix, baseline. Child affinity is CPU 0; observer affinity, host load and CPU counters are retained for every run. No retained samples were discarded and there were no selective retries.

The existing summarizer and fixed gate checker produced each summary and gate output. The combined checker also prints historical runtime-tracing values from its unchanged input; those are not new measurements or claims about runtime tracing in this experiment. The new verifier independently checks all 600 pairs, all six summaries, source and binary identities, and the unchanged profiling-overhead threshold.

The plan, build manifests, exact commands, host snapshots, raw samples, summaries, gate outputs and source-input hashes are retained here. Run python3 benchmarks/verify-profile-order-evidence.py for deterministic verification. The shared local/CI evidence command includes that verifier.
