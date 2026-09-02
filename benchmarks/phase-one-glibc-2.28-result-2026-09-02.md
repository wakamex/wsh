# The glibc 2.28 minimal path narrowly missed two latency gates

The clean rebuild at the tested glibc 2.28 floor passed every correctness, process, lock, repaint, and first-editable gate. The Wakamex renderer also passed both updated-state latency gates. The minimal renderer missed the untracked-state p90 gate by 0.070 ms and the maximum gate by 0.098 ms, so this revision is not an accepted release candidate and the fixed thresholds remain unchanged.

This result remains the failed baseline for the subsequent [one-pass decoder fix](minimal-tail-2026-09-02/report.md), which passed the unchanged 20-iteration gates.

The matched benchmark used the exact bundled Zsh 5.9.2 binary, one 1,000-file Git fixture, and 20 clean, tracked-dirty, and untracked transitions per target. Calibration ran before and after each run, and CPU-pressure telemetry covered every target phase. Staged and detached-HEAD correctness were checked separately.

| Gate | Required | Minimal renderer result | Wakamex renderer result |
| --- | ---: | ---: | ---: |
| Advertised semantics | 100 percent | 62/62 | 62/62 |
| First-editable maximum added over matched raw | At most 2.0 ms | 1.206 ms | 0.793 ms |
| Updated-state p90 added over matched raw | At most 7.1 ms | 7.170 ms | 7.071 ms |
| Updated-state maximum added over matched raw | At most 8.0 ms | 8.098 ms | 7.632 ms |
| Git processes per transition | At most 1 | 1 | 1 |
| Git processes without `GIT_OPTIONAL_LOCKS=0` | 0 | 0 | 0 |
| Repaints for a changed result | At most 1 | 1 | 1 |
| Advertised staged and detached-HEAD checks | 100 percent | 2/2 | 2/2 |

The minimal failure is isolated to untracked settled latency. Its untracked p90 was 7.680 ms against a matched raw p90 of 0.510 ms, and its untracked maximum was 8.646 ms against a matched raw maximum of 0.548 ms. Clean and dirty states passed. The next intervention needs a measured cause and a one-factor counterfactual; changing the gates would discard the purpose of this baseline.

The Wakamex renderer's largest added p90 was 7.071 ms in clean state, and its largest added maximum was 7.632 ms in clean state. Its dirty and untracked states had lower deltas. Both presentations used the same resident runtime and one-process Git provider.

## Run acceptance and host

Both benchmark runs passed the runner's calibration and telemetry admission checks. The minimal run's median CPU-pressure overlap was 0.228 percent; the Wakamex run's was 2.259 percent. The host ran Fedora Linux 44 with kernel 7.1.9-200.fc44.x86_64 on an AMD Ryzen 9 3950X with 32 online logical CPUs.

## Exact identities

The wsh source revision was `afa820b0ffd799f6dbe3dfb1e87354769b55cb5a`. The development bundle manifest digest was `9e87d752aea21ab73747c553c0e1d1c7a37a5c921ffd3db3e4f31e5dc0035edc`, the Zsh binary SHA-256 was `bac80fcae8e1dd2aa1d5b77d5a68a7bb73612f8bf349d1f33e775117b7cd5cfb`, and the runtime SHA-256 was `85f46b8f2b5e49cf13f719b9b9a3b75eeea70f6d1c2fdf73a71ed8d9803776e9`.

The benchmark revision was `8dc0b5fea25671d6745a556bffb740d3866e189c`, and its runner SHA-256 was `352c096f011eb282f12e6d4c12281340fac96b635a2879cc065d7637a6592872`. The bundle used signed upstream Zsh 5.9.2 source with SHA-256 `36fa734374b44783582cec09bcd67822e2f992c779ec1624ab5596df078d2f81`, GCC 8.5.0, GNU ld 2.30, and Rust 1.95.0.

## Retained data

The complete minimal-theme evidence is retained in [`phase-one-glibc-2.28-minimal-2026-09-02/`](phase-one-glibc-2.28-minimal-2026-09-02/), and the Wakamex evidence is retained in [`phase-one-glibc-2.28-wakamex-2026-09-02/`](phase-one-glibc-2.28-wakamex-2026-09-02/). Each directory contains the runner metadata, raw samples, telemetry, target summary, and generated distribution table with their recorded input digests.

The earlier [`phase-one-result-2026-09-02.md`](phase-one-result-2026-09-02.md) remains the result for its glibc 2.35 development build and source identity. This glibc 2.28 rebuild remains the pre-fix compatibility-floor baseline.
