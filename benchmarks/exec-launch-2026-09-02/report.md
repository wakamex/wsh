# Compact state and exec add 2.723 ms at p90 over raw Zsh

The normal glibc 2.28 `wsh` entrypoint reached its first editable prompt in 7.963 ms at p90, 2.723 ms over the raw bundled-Zsh control. The launcher itself accounted for 0.527 ms by p90 difference over the direct complete path and 0.70 ms at the paired median in the isolated launch benchmark. All fixed startup thresholds passed, so this path provides no measured reason to embed the launcher in a Zsh fork.

Activation now writes a compact state record and ordinary startup reads only that record before replacing itself with Zsh through `exec`. The previous activation-backed implementation still parsed the 265 KiB bundle manifest, launched Zsh as a child, and waited for its lifetime. Its baseline manager contribution was 1.156 ms by p90 difference through the first prompt, while the final local path contributed 0.487 ms and the final floor build contributed 0.527 ms.

| Result | Fixed gate | Final local | Final glibc 2.28 | Status |
| --- | ---: | ---: | ---: | --- |
| Isolated paired median launcher overhead | At most 1.0 ms | 0.65 ms | 0.70 ms | Pass |
| Launcher contribution through first prompt, p90 difference | At most 1.0 ms | 0.487 ms | 0.527 ms | Pass |
| Complete managed startup added over raw, p90 difference | At most 5.0 ms | 2.828 ms | 2.723 ms | Pass |
| Complete managed startup added over raw, maximum difference | At most 8.0 ms | 3.716 ms | 1.056 ms | Pass |

## First-editable distributions

Each value below is an independent distribution statistic. An added value subtracts the corresponding raw or direct statistic rather than computing a percentile over per-repetition differences, matching the project's existing added-over-raw convention.

| Build and path | Median | p90 | Maximum |
| --- | ---: | ---: | ---: |
| Baseline raw Zsh | 4.980 ms | 5.120 ms | 5.273 ms |
| Baseline direct complete wsh | 7.177 ms | 7.618 ms | 8.161 ms |
| Baseline managed complete wsh | 8.575 ms | 8.775 ms | 9.032 ms |
| Final local raw Zsh | 4.794 ms | 4.993 ms | 5.260 ms |
| Final local direct complete wsh | 6.933 ms | 7.334 ms | 8.047 ms |
| Final local managed complete wsh | 7.576 ms | 7.822 ms | 8.976 ms |
| Final glibc 2.28 raw Zsh | 5.018 ms | 5.240 ms | 7.241 ms |
| Final glibc 2.28 direct complete wsh | 7.075 ms | 7.437 ms | 7.756 ms |
| Final glibc 2.28 managed complete wsh | 7.835 ms | 7.963 ms | 8.297 ms |

This benchmark measures cold session startup from PTY creation until the first visible prompt. The existing first-editable release gate in the phase-one benchmark measures the prompt returned after a command while asynchronous collection continues. The two quantities answer different questions and retain separate thresholds.

## Compact activation record and process handoff

State schema 2 contains the canonical bundle root, verified manifest identity, path, mode, and size for the shell, runtime, integration adapter, and default theme, and the fixed ZDOTDIR path. It is capped at 16 KiB and rejects unknown fields, unsupported versions, non-normalized launch paths, symbolic links, missing paths, and wrong file types, modes, or sizes.

Activation, rollback, `wsh bundle verify`, and `wsh bundle current` still parse the strict manifest and hash every payload file. Ordinary launch trusts the completed activation and immutable-bundle contract. It reads the compact state once, checks the bundle root, ZDOTDIR, and four launch files, then calls `exec` on the selected Zsh with the matching runtime, theme, bundle root, and ZDOTDIR in its environment. A same-size payload mutation or manifest edit after activation is intentionally outside the startup check and remains detectable by complete verification.

The development-bundle test launches normal activated `wsh`, records `$$` from the resulting Zsh, and requires it to equal the launcher's original PID. This proves the handoff replaces the manager process. The complete floor build also passed the Rust and upstream Zsh suites, relocated-bundle verification, a real provider request, dependency-manifest comparison, PTY repaint, crash, shell-exit cleanup, and the `GLIBC_2.28` symbol ceiling.

## Measurement method and retained evidence

The interactive benchmark starts fresh PTYs for raw bundled Zsh, the bundled Zsh with complete wsh integration and runtime directly, and the activated manager path. All variants use the same clean 1,000-file Git fixture and CPU 0. Each receives five warmups and 40 measured starts split across forward and reverse variant order. Timing begins immediately before PTY creation and ends when the first prompt marker is visible; the runtime is initialized synchronously before the wsh prompt and Git refresh remains asynchronous.

The isolated benchmark executes `-f -c exit` 1,000 times per variant as ten observations of 100 sequential starts, after 20 warmup launches, with forward and reverse order on CPU 0. The final local direct and managed medians were 1.80 and 2.40 ms; paired added observations ranged from 0.50 to 0.80 ms. The floor direct and managed medians were 1.80 and 2.50 ms; paired added observations ranged from 0.50 to 0.70 ms.

The exact measured local manager SHA-256 was `3e98e85b82989e14791a1e240239f044747bce801accec22f9cfc30d0f7e4692`. The exact floor manager SHA-256 was `2050d7151df3f7f65428aa7db196eb60042b74ed3698a0f0ded9de8a4eb9379e`, the floor manifest digest was `df1e2ee21436e8ded5710d53d1b40e41f83fe6b89b74610b51f2b70589b7aa13`, and its Zsh SHA-256 was `bac80fcae8e1dd2aa1d5b77d5a68a7bb73612f8bf349d1f33e775117b7cd5cfb`. [`metadata.txt`](metadata.txt) records the remaining source, bundle, build, benchmark, host, and workload identities.

[`baseline-first-editable.tsv`](baseline-first-editable.tsv) retains the preceding activation-backed baseline. [`final-compact-exec-first-editable.tsv`](final-compact-exec-first-editable.tsv) and [`final-compact-exec-launch.tsv`](final-compact-exec-launch.tsv) retain the final local measurements. [`final-floor-compact-exec-first-editable.tsv`](final-floor-compact-exec-first-editable.tsv) and [`final-floor-compact-exec-launch.tsv`](final-floor-compact-exec-launch.tsv) retain the final compatibility-floor measurements. The fixed hypothesis, thresholds, and one-attempt limit were recorded before the intervention in [`../exec-launch-plan-2026-09-02.md`](../exec-launch-plan-2026-09-02.md).
