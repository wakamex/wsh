# Foreground child startup investigation

Wakterm needs to run an exact provider command as the foreground job and present an interactive shell after it exits. The current restore path converts the provider argument vector into quoted shell text before invoking an interactive login shell. Reported restore, job-control, suspension, and reattachment work make this a high-priority correctness investigation, but they do not yet establish that `wsh` needs a new interface.

## The current wrapper serializes argv through shell text

[`restored_harness_then_shell`](../wakterm/mux/src/session_persistence.rs) reads the configured shell, quotes each provider argument with `shell_words`, joins the result into one command string, and invokes:

```text
shell -l -i -c '<reconstructed provider command>; exec "$0" -l'
```

This is concrete implementation complexity. The experiment must still isolate which reported failures are caused by argument reconstruction, interactive-shell startup, process-group ownership, provider behavior, or restoration policy.

## Positional arguments are the cheapest counterfactual

The first comparison passes the original argument vector after the `-c` program and executes it through positional parameters:

```text
shell -l -i -c '"$@"; exec "$0" -l' shell <exact provider argv...>
```

The test harness records provider exit status separately and must account for shells whose login or interactive option syntax differs. The important counterfactual is `"$@"`: the provider executable and arguments remain distinct and are not reconstructed as shell source. It also removes the current wrapper's requirement that every restored harness argument convert to UTF-8.

If this wrapper passes every required case, Wakterm should adopt the local fix and `wsh` should not add foreground-launch machinery.

## The reproducer separates correctness layers

The fixture provider records `/proc/self/cmdline`, PID, process group, and `tcgetpgrp`, and exposes deterministic modes for normal exit, nonzero exit, signal handling, terminal input, suspension, continuation, and child creation. Tests compare the current wrapper and positional-argument wrapper in a fresh PTY under Bash, Zsh, and the `/bin/sh` fallback.

| Case | Required observation |
|---|---|
| Exact argv | Empty arguments, spaces, quotes, newlines, wildcard characters, dollar signs, leading dashes, and non-ASCII bytes accepted by the platform arrive unchanged |
| Foreground ownership | The provider process group owns the controlling terminal while it runs and can read terminal input |
| Interrupt | Ctrl-C reaches the foreground provider and the shell returns to an editable prompt afterward |
| Suspend and continue | Ctrl-Z stops the provider in the shell job table, `fg` resumes it, and terminal ownership transfers correctly |
| Exit and reaping | Normal, nonzero, and signalled exits leave no zombie and produce one subsequent prompt |
| Nested children | A provider child remains in the expected job and signal domain |
| Shell selection | Configured supported shells retain documented login and interactive behavior |
| Repeated restoration | Repeating the launch does not accumulate shell layers, stale jobs, or terminal modes |

The test records argv fidelity, process IDs, process-group IDs, foreground process-group transitions, wait status, signal observations, prompt count, and terminal mode before and after the provider.

Pure argument tests belong beside Wakterm's existing `restored_harness_runs_as_a_shell_child` test. One ignored Unix PTY test can live beside them using Wakterm's existing `portable_pty` dependency. A changed argv byte sequence, wrapper construction failure, incorrect foreground process group, lost suspended job, `fg: no current job`, missing prompt, or zombie is a correctness failure.

## A wsh interface requires a failed local counterfactual

Only a failure attributable to shell startup or job-control mechanics can justify a `wsh` interface such as:

```text
wsh --run-foreground -- <exact argv...>
```

An accepted interface would have to start the exact argument vector without evaluation, establish the foreground process group and controlling terminal, integrate suspend and continue with the interactive job table, reap the child, restore terminal modes, and enter one normal prompt afterward.

Wakterm would continue to own executable selection, arguments, environment, cwd, provider session, restore policy, and whether a foreground provider should be launched. `wsh` would own only the demonstrated shell transition that Wakterm cannot implement cleanly with the positional wrapper. Even a failed Wakterm wrapper does not establish a shared `wsh` feature unless another launcher needs the same owner or the failure follows from shell-specific job-control behavior that belongs in the distribution.

## Performance is secondary to correctness

The comparison records time from PTY creation to provider readiness and from provider exit to an editable prompt, but small latency differences do not justify the interface if the local wrapper is correct. Process count and retained shell layers are useful supporting measurements. The primary gate is job-control and argv correctness.
