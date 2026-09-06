# Native editor-readiness measurement passes the profiling overhead gate

The profiling benchmark now waits for the bundled Zsh's native OSC 133 `B` marker after ZLE line-init hooks. Profiling adds 2.396 ms at p90 across 100 normal/profile pairs, below the unchanged 3.000 ms limit. A delayed-hook regression proves that earlier visible prompt text is insufficient: the old observer reported 5–7 ms despite a required 200 ms initialization delay, while the corrected observer recorded at least 228 ms.

The comparison used the same existing Zsh PTY harness, default Wsh configuration, 1,000-file Git fixture, affinity, warmups, and paired ordering. No profiling runtime optimization was needed. The report now labels its own callback milestone `Wsh ZLE initialization hook` and its runtime hook span `Wsh first precmd hook`.

## Latency and gates

| Measurement | Normal Wsh | Profiled Wsh | Paired profile overhead |
|---|---:|---:|---:|
| First editor readiness median | 26.997 ms | 28.907 ms | 1.910 ms |
| First editor readiness p90 | 27.700 ms | 29.996 ms | 2.396 ms |
| Settled Git prompt median | 36.644 ms | 38.676 ms | See raw paired samples |
| Settled Git prompt p90 | 37.654 ms | 39.932 ms | See raw paired samples |

| Gate | Limit | Observed | Result |
|---|---:|---:|---|
| Default profile editor-readiness paired p90 overhead | 3.000 ms | 2.396 ms | Pass, newly measured |
| Isolated runtime-ready p90 trace overhead | 3.000 ms | 1.688 ms | Pass, retained unchanged-runtime evidence |
| Isolated runtime-refresh p90 trace overhead | 0.500 ms | 0.458 ms | Pass, retained unchanged-runtime evidence |

The runtime executable remains identical by SHA-256 to the runtime used for the earlier isolated trace experiment. Those two runtime measurements were reused with their original identity; they were not rerun or represented as new measurements. The end-to-end refresh difference remains diagnostic because it includes independent Git scheduling and PTY observation.

## Readiness contract

In the pinned Zsh source, `zleread` calls the line-init hook before `start_edit`; `start_edit` emits the native `integration-prompt` sequence containing OSC 133 `B`. [The retained source excerpt](native-readiness-source.txt) identifies the exact files and lines. Wsh's existing source patches do not change that ordering.

`tests/profile-readiness.zsh` supplies a synthetic startup file that prints prompt-like text early and installs a 200 ms line-init delay. It runs the actual benchmark with normal and profiled shells. The visible-prompt control and native-marker candidate differ only in their readiness condition; both have the same optional startup-fixture support. The old condition fails all four delayed measurements. The new condition passes all four and requires the settled measurement to follow readiness. Both raw test outputs are retained.

The production profile's ZLE timestamp still comes from its own callback. It can precede callbacks registered later, so its display label names that callback rather than claiming complete editor readiness. The first runtime `precmd` span likewise excludes other user and theme hooks. Event names and schema remain unchanged, so old profile files remain readable. The acceptance benchmark independently observes the native marker and needs no additional timing hook.

## Validation and evidence

The delayed regression, profile privacy/recovery test, and complete locked Rust workspace tests passed. The bundle test runner now includes the delayed regression, and retained-evidence CI checks the corrected samples and fixed gates. The canonical glibc 2.28 suite and live GitHub CI were not run in this task. The measured bundle is an unsigned host development artifact.

The [plan](../profile-readiness-plan-2026-09-05.md), [source and build identities](metadata.json), compressed [bundle manifest](bundle-manifest.json.gz), [raw samples](native-samples.tsv), [summary](native-summary.tsv), [gates](gates.tsv), [visible-prompt regression](delayed-visible-control.log), [native-marker regression](delayed-native.log), [profile correctness](profile-correctness.log), and [Rust test log](cargo-test.log.gz) retain the experiment. No latency observations were excluded. `SHA256SUMS` binds inputs, evidence and verification tools.

The earlier real-configuration matrix used a different harness and extra observer hooks. Its 3.079 ms empty-configuration result and workload-specific failures remain historical observations. This corrected standard-fixture pass does not claim that every arbitrary user configuration has less than 3 ms profile overhead. Historical profile evidence is now checked against committed source `3decf521a13d98b9e0f50c64c666766406800205`, preserving its original inputs rather than updating old hashes to match new implementation.

## Reproduction

```sh
./build/build-development-bundle.zsh
zsh tests/profile-readiness.zsh target/release/wsh <bundle>
zsh tests/profile.zsh target/release/wsh <bundle>
./benchmarks/benchmark-profile.zsh <new-samples.tsv> target/release/wsh <bundle> 50
./benchmarks/summarize-profile.zsh <new-samples.tsv> <new-summary.tsv>
./benchmarks/check-profile-gates.zsh <new-summary.tsv> benchmarks/profile-2026-09-05/runtime-trace.tsv
./benchmarks/verify-profile-readiness-evidence.zsh
```

The delayed old-observer control uses the decompressed `visible-prompt-control.zsh.gz` as the third argument to `tests/profile-readiness.zsh` and is expected to fail. Runtime-gate reuse is valid here because the executable and its trace behavior are unchanged; a runtime change requires a new isolated measurement.
