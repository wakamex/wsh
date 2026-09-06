# Wsh profiling

`wsh profile` launches the active bundle through the normal Wsh startup path and records startup costs and the initial asynchronous Git prompt update. Exit the shell to print a report.

```sh
wsh profile
```

The default profile separates launcher handoff, user startup files, Wsh defaults, runtime startup, Wsh's first runtime `precmd` hook, Wsh's first ZLE initialization callback, repository discovery, the Git child process, Git output parsing, prompt rendering, response writing, snapshot publication, and Zsh repaint application. It also reports the exact Wsh bundle and Zsh source identities, active theme, and ownership of the three bundled editing defaults.

Use function mode when the startup-level spans do not isolate the cost:

```sh
wsh profile --functions
```

Function mode loads Zsh's native `zprof` module and reports the eight functions with the highest self time. It changes the measured workload, so compare function-mode runs only with other function-mode runs.

## Profile recovery

Wsh prints the profile directory when the session starts. A clean shell exit prints the report automatically. The trace remains useful after an interrupted session and can be summarized directly:

```sh
wsh profile report ~/.local/share/wsh/profiles/PROFILE
```

Events that have not happened or were not retained are reported as `unavailable`. A live report can therefore show the completed portion of a session without treating missing measurements as zero.

## Privacy and bounds

Default profiles do not record command text, prompt contents, provider output, environment contents, current directories, repository paths, or paths to user startup files. Startup files are identified only by their standard names, such as `.zshrc`. The private metadata sidecar contains the selected bundle path so the reporter can resolve its manifest after launch.

Each session directory is created with mode 0700 beneath the Wsh state directory. Trace, metadata, and optional `zprof` files are created with mode 0600 without following symbolic links. The combined trace is bounded at 8 MiB, individual trace lines at 64 KiB, the event count at 100,000, and `zprof` output at 1 MiB. The reporter rejects unsupported schemas, unknown fields, incomplete events, oversized inputs, symbolic links, and files or directories accessible to other users.

## Scope

The current profile covers Wsh's implemented startup and Git prompt path. It records Zsh lifecycle boundaries around Wsh hooks but does not observe the native OSC byte producer internally. Completion and pane-history attribution will be added only if those features pass their own evidence gates. System-call tracing, stack sampling, and third-party function instrumentation remain developer tools.

The [accepted experiment](benchmarks/profile-2026-09-05/report.md) records the baseline, correctness fixture, instrumentation overhead, exact bundle identity, and retained raw measurements.

The [readiness correction](benchmarks/profile-readiness-2026-09-05/report.md) makes the acceptance benchmark wait for native OSC 133 `B`, after ZLE line-init hooks. It passes the unchanged 3 ms overhead gate at 2.396 ms p90 on the standard fixture. `Wsh ZLE initialization hook` is the profile callback milestone, and `Wsh first precmd hook` measures only the runtime hook; earlier or later user hooks remain outside those named spans. Use function mode to investigate them. The [real-configuration matrix](benchmarks/real-config-2026-09-05/report.md) retains separate workload-specific overhead and attribution results.

Prompt selection also applies to profiling: `wsh profile` preserves the existing prompt by default, while `WSH_THEME=minimal wsh profile` includes Wsh presentation and its Git collector. Existing-prompt sessions have no Wsh runtime spans. Current Wsh-renderer benchmark harnesses select `WSH_THEME=minimal` explicitly; historical evidence retains its original configuration.

The Directory jumping span measures the built-in directory-jump adapter and any plugin initialization it owns. When an existing OMZ or custom command is preserved, that implementation loads within the user startup span instead.
