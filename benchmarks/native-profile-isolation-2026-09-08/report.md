# Native profiles exclude inherited child-shell events

A profiled shell now keeps its profiling parameters local before user startup. Its runtime receives only the trace settings it needs through the runtime-start function's local environment. Seven real-shell isolation cases pass in normal and sanitized builds, and both native and legacy runtime attribution still work. Default profiling adds 2.013 ms paired p90 with the existing prompt and 2.210 ms with Minimal on 100 alternating pairs each, below the unchanged 3 ms gate.

| Measurement | Observed | Predeclared gate |
|---|---:|---|
| Existing prompt default profile overhead, 100 pairs | 2.013 ms paired p90 | At most 3 ms, pass |
| Minimal prompt default profile overhead, 100 pairs | 2.210 ms paired p90 | At most 3 ms, pass |
| Unprofiled existing prompt regression, 50 matched pairs | +0.367 ms paired p95 | At most +3 ms, pass |
| Unprofiled Minimal prompt regression, 50 matched pairs | +0.416 ms paired p95 | At most +3 ms, pass |

## Reproduction and correction

The baseline noninteractive parent never initialized interactive components, yet its saved trace contained a child's directory jumping, history, autosuggestion and highlighting spans plus a shell-exit event. Both the child and parent ran the real native binary. The parent preserved status 19, but the trace attributed work to the wrong session.

Native startup now clears the export attribute of profiling parameters before any user startup file, while preserving their local values. The shared runtime-start function temporarily exports `WSH_TRACE_FILE` and `WSH_PROFILE_STARTED_UNIX_US` for its own helper. Ordinary explicit runtime tracing retains its existing behavior. This uses the existing parameter and process boundaries without adding an ownership token or a special child-shell protocol.

The first candidate fixed ordinary Zsh startup but left profile exports in `--emulate sh`, which bypasses Wsh's Zsh-specific resource setup. The final candidate performs profile preparation at the common native startup boundary. A separate sanitizer-workbench edit initially inserted that call at the wrong repeated source line; the retained compiler failure led to a function-scoped correction. The locked production patch had the correct context throughout that workbench error.

## Verification

The seven isolation cases cover a child command, a child during `.zshenv`, `-f`, ordinary external environment inheritance, `--emulate sh`, an independently profiled child, and missing Wsh integration. Child invocations must return their expected status 3; the parent returns 19. Parent traces exclude child components, and an explicit child profile receives its own private directory.

Normal and scoped whole-Zsh ASan/UBSan builds pass isolation, all eleven native lifecycle cases, profile attribution/privacy/argv tests, and nine private-storage/status cases. The normal candidate also passes 75 upstream scripts with zero failures and two skips, 18 startup cases, nine Wsh integration suites including real OMZ profile modes, 45 saved-reader boundaries, and the 200 ms late-editor readiness observer. A separate freshly assembled legacy bundle passes the existing end-to-end profile regression with the changed shared adapter. Existing standalone parser and buffer sanitizer coverage remains in the preceding two reports; this change adds no parser.

Timing runs are sequential on CPU 0 after correctness. The unprofiled control retains the preceding native executable and runtime adapter; only the three unrelated compiled-path-dependent resource files are copied from the candidate. Thus this comparison includes both the native parameter change and the shared adapter change. Source snapshots, matched resource identities, candidate manifest, exact commands, raw samples and all failures are retained in `inputs.tar.gz`, `results.tar.gz`, `manifest.json.gz` and [metadata.json](metadata.json). The historical builtins/theme verifier now reads the original adapter from its existing pinned historical commit; none of its original hashes were changed.

## Stage 4 result and retained boundaries

The native interface now owns profile invocation, private storage, native startup timestamps, normal-exit reporting and saved-report decoding. The 115-line shell adapter remains for the currently shell-owned component callbacks, initial ZLE callback and upstream function profiler. Its function table describes initialization through the first editable prompt; sessions that never reach that checkpoint can report it as unavailable. These adapters remain counted in later component comparisons. No Rust manager is needed to profile a native session or read its saved report.

The recorded-identity and signed-64-bit numeric reader differences from legacy reports remain explicit migration decisions in the [invocation/report result](../native-profile-2026-09-08/report.md). Default startup/runtime instrumentation gates pass across the retained stage-4 experiments. These are unsigned local development builds. Final package dependencies, target-floor validation, migration of production consumers and release qualification remain stage-10 work.
