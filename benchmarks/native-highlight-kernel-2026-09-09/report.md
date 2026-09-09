# Native command classification does not materially accelerate highlighting

Keep the existing highlighter. The private C command-classification branch passes the upstream main-highlighter suite and sanitizer run, but complete highlighting improves by only 1.13% on the distinct 100-command cold-cache workload. The fixed adoption gate required 20%. Several 100-command paired p95 changes also exceed the +1 ms regression limit. The candidate does not justify another native interface.

| Complete highlight workload | Reference median | C classifier median | Paired p95 change |
|---|---:|---:|---:|
| Short command, cold cache | 0.831 ms | 0.820 ms | +0.137 ms |
| Short command, reusable cache | 0.788 ms | 0.790 ms | +0.232 ms |
| 100 repeated commands, cold cache | 78.535 ms | 78.580 ms | +1.558 ms |
| 100 repeated commands, reusable cache | 79.551 ms | 79.408 ms | +1.296 ms |
| 100 distinct commands, cold cache | 85.250 ms | 84.285 ms | +1.196 ms |
| 100 distinct commands, reusable cache | 81.724 ms | 81.920 ms | +2.077 ms |
| Multiline conditional, cold cache | 4.144 ms | 4.110 ms | +0.106 ms |
| Multiline conditional, reusable cache | 2.717 ms | 2.715 ms | +0.143 ms |

## Retain the rejected prototype

The candidate replaces only the branch that classifies aliases, reserved words, functions, builtins and commands. It invokes the same native parameter tables, retaining cache ownership, unknown-command fallback, parsing, styles and editor lifecycle in the upstream implementation. The existing precmd-cleared cache remains active in both variants. No complete C parser or syntax highlighter has been established, and this focused result does not justify building one as a roadmap gate. A future complete port needs a separate simplification case and the same compatibility evidence.

The C module and fixture transformation remain available for inspection. No production code, user configuration or upstream dependency was replaced. The native directory, lazy-history and suggestion prototypes are separate results; their timing gains do not transfer to highlighting.

## Tests and method

Start from `caceaaa` and the unsigned native installation recorded in metadata. Both variants use the exact shipped main-highlighter source, whose digest matches the pinned upstream checkout, and that checkout's actual test corpus. Release control and candidate runs pass the suite. The instrumented host and C module also pass with the documented upstream leak/function-sanitizer exceptions and no diagnostics. The initial absolute-path test invocation failed in the harness; the corrected runs use a relative invocation from the suite root and a private home. Initial outputs remain retained.

Each of eight workloads has 50 alternating matched pairs on CPU 0. Function selection, cache reset and optional warm-cache painting occur outside the timed complete `_zsh_highlight_highlighter_main_paint` call. Both variants produce identical nonempty region-highlight arrays in all 400 pairs. The paired p95 is the 48th sorted difference of 50. All samples are retained; the failed thresholds are not relaxed or explained away. The large buffers deliberately contain 100 complete commands and do not represent ordinary single-command typing.

The source, private transformed fixture trees, upstream tests, exact commands, build identities, raw TAP logs and all timing/output rows are archived. The evidence verifier checks the suite outcomes, exact highlight-span parity, arithmetic and the failed gates.
