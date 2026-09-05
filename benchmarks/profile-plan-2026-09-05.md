# End-to-end profile experiment

Wsh can record bounded runtime events through `WSH_TRACE_FILE`, but a user cannot invoke or summarize that trace, and it begins only when `wsh-runtime` starts. The current path therefore cannot answer which part of launcher handoff, user startup, bundled defaults, runtime startup, initial Git collection, prompt rendering, or editor readiness made startup slow.

## Baseline

- Source revision: `d15f9a2bc1075122796a6b7c0bafaa981ee7caf0`
- Bundled Zsh source: `cad0d67c76e2be7371cf3526b79ea2581810d35a`
- Existing interface: `WSH_TRACE_FILE`, accepted runtime trace schema version 1
- Reproducer: `cargo run -q -p wsh -- profile`
- Observed result: the manager rejects `profile` and prints usage
- Existing trace scope: runtime readiness, refresh receipt, cancellation, combined Git-worker duration, snapshot publication, repaint cause, and shutdown

## Smallest counterfactual

Keep the existing runtime trace and add one manager-owned profile session around the normal `exec` launcher. The manager creates a private bounded trace, establishes one cross-process timestamp origin, and then follows the unchanged shell launch path. Thin Zsh probes bracket only startup files and Wsh-owned integration phases. A one-shot ZLE hook records the first actually editable buffer. On shell exit, the existing manager parses and summarizes the trace. Optional `--functions` mode loads Zsh's native `zprof` for function-level attribution because enabling it changes the measured workload.

This avoids a resident profiler, a second shell supervisor, a tracing daemon, command capture, arbitrary startup parsing, and a native Zsh module.

## Acceptance gates

The first implementation gets one attempt and must pass all of these gates:

1. `wsh profile` launches through the same shell entrypoint, user startup order, runtime, theme, and ZLE path as `wsh`.
2. The trace identifies the manager version, bundle digest, Wsh source, Zsh version and source, target, theme, and enabled built-in ownership without recording command text, environment contents, paths to user startup files, repository paths, prompt contents, or provider output.
3. The trace attributes launcher handoff, each applicable user startup file, each bundled editing default, runtime readiness, first `precmd`, first ZLE readiness, initial provider work, rendering and publication, repaint application, and shell exit.
4. The report states time to the first editable prompt and separately reports asynchronous initial provider completion. Missing optional events are named as unavailable rather than treated as zero.
5. The trace is a regular file beneath a mode-0700 profile directory, created mode 0600 without following a pre-existing path, bounded at 8 MiB, and parsed with bounded lines and fields. Malformed or unsupported traces fail closed.
6. Profiling remains opt-in. Ordinary `wsh` startup creates no profile file, performs no profile writes, and starts no profile process.
7. Default-profile first-editable p90 overhead remains at most 3.0 ms and initial runtime refresh p90 overhead remains at most 0.5 ms over the same untraced workload, preserving the existing resource gates. Optional function mode is measured separately because loading `zprof` deliberately changes the workload.
8. The profile summary adds no work before the measured session exits. Interrupted sessions retain their trace for explicit `wsh profile report <trace>` recovery.

## Scope

The first report covers current Wsh startup and Git prompt behavior. It records the Zsh lifecycle boundaries from Wsh hooks but does not claim to observe the native OSC byte producer internally. Completion and pane-history attribution enter their own later experiments when those features exist. General sampling, stack profiling, syscall tracing, and third-party function instrumentation remain developer-tool concerns until a reproduced question requires them.
