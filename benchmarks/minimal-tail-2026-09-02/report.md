# One-pass prompt decoding closes the standard glibc 2.28 latency gate

The minimal renderer now passes the unchanged glibc 2.28 release gates. Its worst updated-state result added 6.711 ms at p90 and 6.911 ms at maximum over matched raw Zsh, below the fixed 7.1 ms and 8.0 ms limits. The accepted 20-iteration run used the exact bundled Zsh 5.9.2 binary, one 1,000-file Git fixture, and clean, tracked-dirty, and untracked transitions.

Profiling isolated a byte-at-a-time prompt decoder in the Zsh integration. Replacing it with one whole-string transformation reduced median decode time from 279.555 to 93.266 microseconds per field, or 66.6 percent, in a position-reversed microbenchmark with ten 10,000-call measurements per implementation. The integration decodes both left and right prompt fields when a snapshot changes. A PTY regression test round-tripped every non-NUL byte before the benchmark was accepted.

| Gate | Required | Fixed minimal result |
| --- | ---: | ---: |
| Advertised semantics | 100 percent | 62/62 |
| First-editable maximum added over matched raw | At most 2.0 ms | 0.891 ms |
| Updated-state p90 added over matched raw | At most 7.1 ms | 6.711 ms |
| Updated-state maximum added over matched raw | At most 8.0 ms | 6.911 ms |
| Git processes per transition | At most 1 | 1 |
| Git processes without `GIT_OPTIONAL_LOCKS=0` | 0 | 0 |
| Repaints for a changed result | At most 1 | 1 |
| Advertised staged and detached-HEAD checks | 100 percent | 2/2 |

## The decoder was measurable independently of Git

The runtime sends rendered left and right prompt fields as hexadecimal text so arbitrary prompt bytes cannot break the newline-delimited shell protocol. The Zsh integration decodes those fields into the exact `PROMPT` and `RPROMPT` byte strings after the provider and renderer return.

The old `_wsh_hex_decode` consumed two hexadecimal characters per shell loop iteration, called the Zsh `printf` builtin for every decoded byte, and appended each byte to an output parameter. A prompt with dozens of bytes therefore required dozens of parameter slices, loop branches, builtin calls, and string appends for each side. The counterfactual preserves the wire format: one Zsh pattern substitution rewrites every two-character pair in the complete input from forms such as `1b` and `5b` to `\\x1b` and `\\x5b`, then one `printf -v REPLY '%b'` decodes the complete string. This removes shell-loop overhead without changing Git collection, Rust rendering, protocol messages, or prompt contents.

The retained [`hex-decode.tsv`](hex-decode.tsv) contains five forward-order and five reverse-order measurements for each implementation after warmup. The median improvement was 186.289 microseconds per field. This microbenchmark establishes the local decoder cost; the matched PTY benchmark below measures the complete prompt consequence.

The PTY regression covers byte values 1 through 255. NUL remains outside the newline-delimited shell protocol's supported prompt payload, and the runtime already rejects control characters that themes could introduce as literals.

## The fixed 20-iteration run passes every release gate

| State | Raw p90 | wsh p90 | Added p90 | Raw maximum | wsh maximum | Added maximum |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Clean | 0.518 ms | 7.167 ms | 6.649 ms | 0.543 ms | 7.431 ms | 6.888 ms |
| Dirty | 0.410 ms | 7.121 ms | 6.711 ms | 0.447 ms | 7.264 ms | 6.817 ms |
| Untracked | 0.461 ms | 7.122 ms | 6.661 ms | 0.466 ms | 7.377 ms | 6.911 ms |

The run also retained raw Zsh, direct one-scan Git, idle-runtime, and trace-enabled controls. All 60 timed semantic checks and the staged and detached-HEAD checks passed. Every changed result used one Git process, zero processes without optional-lock suppression, and one repaint. The runner accepted both timing calibrations and a median CPU-pressure overlap of 0.135 percent.

The broader Wakamex presentation also passed from the clean fixed bundle. Its worst first-editable maximum added 0.683 ms, its worst updated-state p90 added 6.688 ms, and its worst updated-state maximum added 7.211 ms. All 62 semantic checks passed with one optional-lock-safe Git process and one repaint per changed result.

## A 100-iteration stress run shows the improvement and one residual outlier

The pre-change 20-iteration reproduction already passed, so it could not independently reproduce the earlier 0.070 ms p90 and 0.098 ms maximum misses. A 100-iteration diagnostic reproduced the tail problem across states: its worst added p90 was 7.558 ms and its worst added maximum was 8.987 ms. After the decoder change, the worst added p90 was 7.074 ms and the worst added maximum was 8.057 ms. The latter came from one 8.516 ms dirty-state sample against a 0.459 ms raw maximum and exceeded the 8.0 ms limit by 0.057 ms.

The fixed release gate uses the benchmark runner's declared 20 iterations, while the 100-iteration runs are retained stress diagnostics with a different sampling contract. The stress comparison supports the decoder change because all three p90 deltas improved and the worst maximum delta fell by 0.930 ms, but it also records remaining host-scheduling sensitivity rather than treating the longer run as an accepted release result.

## Exact identities and retained data

The pre-change stress source revision was `5d6a16366471e3437facca61fbba9f176abfac75`. The fixed source revision was `77a40bd57a17c8bb24cbf6f294f8e238a01429dc`. The clean fixed bundle manifest digest was `e8fbcbb52e58f4cf334794efe2e432c431db79676da6693fd7ba1834679f2055`, and its canonical archive SHA-256 was `0d8bafb2edc9cd308ff889eb58007e5495114a95a6e979d0d39c428bbb20911e`.

The measured minimal payload was byte-identical to the clean canonical bundle above across every bundled path, mode, size, and SHA-256. The measured Zsh SHA-256 was `bac80fcae8e1dd2aa1d5b77d5a68a7bb73612f8bf349d1f33e775117b7cd5cfb`, the runtime SHA-256 was `4fa59ffc191c59db064dad44f47534cf47ac08da6f35e1710935fd0f39477918`, the integration SHA-256 was `2fc5fd142bd28d98f0a71c01f59be565fbade54b231c1d5c8d6afc4480d19f76`, and the minimal theme SHA-256 was `fc2b6516ca20650d3bb795c52a0122ed76272fc34696e95cbcde31ff958b5482`.

The benchmark revision was `8dc0b5fea25671d6745a556bffb740d3866e189c`, and its runner SHA-256 was `352c096f011eb282f12e6d4c12281340fac96b635a2879cc065d7637a6592872`. The bundle used signed upstream Zsh 5.9.2 source with SHA-256 `36fa734374b44783582cec09bcd67822e2f992c779ec1624ab5596df078d2f81`, GCC 8.5.0, GNU ld 2.30, and Rust 1.95.0.

The [`baseline/`](baseline/) and [`fixed/`](fixed/) directories contain the 20-iteration reproducer and fixed minimal run. The [`fixed-wakamex/`](fixed-wakamex/) directory contains the clean-bundle Wakamex confirmation. The [`baseline-100/`](baseline-100/) and [`fixed-100/`](fixed-100/) directories contain the stress diagnostics. Each benchmark directory retains metadata, every raw sample, telemetry, target summaries, and generated distribution tables. The earlier fixed-gate failure remains in [`../phase-one-glibc-2.28-result-2026-09-02.md`](../phase-one-glibc-2.28-result-2026-09-02.md).
