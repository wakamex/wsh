# Foreground startup and job lifecycle investigations

Wakterm has two separate foreground-process needs. It must launch an exact provider command as a foreground job and present an interactive shell after it exits. It must also retire terminal metadata when that job finishes while preserving it across suspension and continuation. Both have concrete Wakterm reproducers, but neither currently establishes that `wsh` needs a new interface.

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

## Managed identity follows the native frontend process

A managed Codex remote TUI can be interrupted with Ctrl-C, return to its shell, and then be replaced by an ordinary Codex TUI in the same pane. Wakterm retained the managed identity because its metadata described the provider thread but did not identify the native frontend process that owned the foreground job. The replacement could therefore inherit a stale managed label even though it was a different local program instance.

Ctrl-Z has different semantics. The managed frontend remains alive and stopped in the shell job table. `fg` should resume the same process and retain the same managed binding. A raw Ctrl-C notification cannot distinguish an application that exited from one that consumed the signal and kept running, so input bytes or signal intent cannot serve as job completion.

The [Wakterm local fix](https://github.com/wakamex/wakterm/commit/4ad5fdf4860847f594b4c310a264ae9856c25b20) records the verified remote TUI PID and process start time after startup. It retains that identity while the process is stopped and clears managed metadata when the frontend disappears or the process tree contains a replacement. It reuses Wakterm's existing 300 ms process-snapshot cache rather than adding another watcher or prompt hook. This is the current owner-local counterfactual.

## The reproducer distinguishes exit, suspension, and consumed signals

The cheapest retained comparison runs the parent of the Wakterm fix and the fixed revision against the same PTY and process-snapshot fixture:

| Transition | Required identity result |
|---|---|
| Managed remote TUI starts | Record its exact PID and start time after the frontend is verified |
| Ctrl-C exits the TUI | Clear managed metadata after the process snapshot no longer contains that frontend |
| Ctrl-C is consumed | Preserve the binding because the verified frontend remains alive |
| Ctrl-Z stops the TUI | Preserve the binding and the same PID and start time |
| `fg` continues the job | Resume the same binding without creating a replacement identity |
| Ordinary TUI starts after managed exit | Do not transfer the managed provider thread or label to the new frontend |
| PID is reused or the process is replaced | Reject the old binding when the start time or verified frontend shape changes |

The correctness metric is zero stale bindings after exit or replacement and zero cleared bindings across stop and continue. The comparison also records time from observable process exit to metadata removal, process-snapshot calls, and refresh latency. The fixed path should stay within the existing 300 ms cache policy and add no process, prompt hook, or independent polling loop. A cache-bounded result is sufficient unless a reproduced UI operation remains stale long enough to be incorrect.

## A reusable contract would report foreground-job transitions

The smallest plausible shell-owned contract identifies one shell-local job generation and process group, then emits ordered `started`, `stopped`, `continued`, and `finished` transitions. `finished` carries the exit or signal status after the shell has observed job completion. A new generation prevents process-group reuse from reviving old metadata. Consumers map that ephemeral job to their own application identity; the process group itself is not a provider thread, pane identity, durable route, or security authority.

Ordinary `preexec` and `precmd` hooks can bracket a simple foreground command, but they do not expose every transition at the point where Zsh assigns the foreground process group or updates its job table. A precise contract may require a small Zsh module or paired Zsh change. That cost is unjustified while Wakterm's cached process identity passes the reproducer.

The `wsh` contract becomes an implementation candidate only if the local fix leaves a measured stale window or polling cost, a shell transition cannot be inferred correctly from process snapshots, or a second consumer demonstrates the same ordered-state need. An accepted result must let Wakterm remove corresponding process-lifecycle inference rather than run both owners.

## Remote and container process identities stay local to their namespace

The reproduced remote TUI is a local Codex frontend connected to a remote provider, so its local PID and start time are valid Wakterm evidence. If the frontend itself runs across SSH or inside a container, a host process tree may expose only the SSH client, container monitor, or namespace proxy. PID and process-group values are meaningful only to the process namespace that observed them.

A later event must therefore include an opaque shell-local generation and an explicit execution context when it crosses a terminal or mux boundary. The shell running in the remote or container context owns job transitions there, while Wakterm owns any mapping back to a local pane and provider session. No raw PID or process group becomes a durable cross-host identity or authorization token.

## Foreground-job events remain behind earlier lifecycle work

For `wsh`, this is a concrete but deferred investigation. The exact-argv foreground-startup counterfactual and the OSC command-lifecycle comparison remain earlier because they can remove existing wrappers and injected shell integration. Foreground-job events come next, ahead of pane-history and completion work, only if the Wakterm fixture demonstrates a remaining gap or another terminal consumer appears. The passing owner-local fix otherwise remains the accepted solution.
