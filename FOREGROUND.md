# Foreground startup and job lifecycle

Wakterm needs to launch an exact provider command as the first foreground job and present an interactive shell after it exits or stops. Wsh provides that transition through `wsh -- <command> [arguments...]`, with `wsh run-foreground` as the explicit form. Wakterm's existing process cache now passes the separate managed-identity lifecycle fixture, so no new foreground-job event protocol is planned.

## Both shell wrappers lose stopped jobs

Wakterm commit `4ad5fdf4860847f594b4c310a264ae9856c25b20` quotes each provider argument, joins the result into shell source, and invokes:

```text
shell -l -i -c '<reconstructed provider command>; exec "$0" -l'
```

The positional-argument counterfactual removes source reconstruction and preserves the original argument vector:

```text
shell -l -i -c '"$@"; exec "$0" -l' shell <exact provider argv...>
```

Both wrappers replace the shell after the provider stops. The replacement does not own the stopped job, and `fg` reports `fg: no current job`. The current Wakterm unit test passes one argument containing spaces but does not exercise suspension, Unix non-UTF-8 arguments, foreground process groups, signals, reaping, or terminal state.

## One interactive Zsh owns the application and prompt

The accepted command is:

```text
wsh -- <command> [arguments...]
wsh run-foreground [--state-root <directory>] [--login] -- <command> [arguments...]
```

The manager reads the compact active-bundle state and replaces itself with the bundled Zsh using `-i -s`. Bundle startup captures the remaining positional parameters before user startup files run. A one-shot `precmd` hook removes itself and executes the captured array directly. That Zsh owns the foreground job, retains it in its job table across Ctrl-Z, and becomes the normal prompt without a second shell initialization. An explicit `--bundle` remains available for diagnostics but performs full bundle verification and is intentionally outside the installed startup timing path.

Wakterm continues to own executable selection, arguments, environment, cwd, provider session, restore policy, and whether the shell is a login shell. It can pass an argument vector to Wsh without constructing shell source. Wsh owns the exact transition into its bundled Zsh and no application identity or restore policy.

## The PTY fixture covers job-control and coexistence behavior

The retained C probe records byte-exact arguments, PID, process group, terminal foreground process group, signals, and a nested child. The PTY test covers normal and nonzero exit, default and consumed Ctrl-C, Ctrl-Z followed by `fg`, terminal-mode restoration, login and non-login startup files, an existing alias and `precmd` hook, twenty fresh repeated launches, process exit, and zombie detection.

Every correctness case passed. Empty arguments, whitespace, quotes, newlines, wildcard characters, dollar signs, leading dashes, Unicode, and a Unix byte sequence containing `0xff` arrived unchanged. The foreground process group owned the terminal, a nested child remained in that group, consumed Ctrl-C produced no premature prompt, and `fg` resumed the same PID and process group after Ctrl-Z. The concise and explicit forms behave identically, and the first application is enclosed by OSC 133 `C` and `D` before native Zsh emits the first editable prompt. Disabling native integration through `.term.extensions` suppresses those markers as well.

## Startup cost stays within the fixed gates

The comparison used the same complete development bundle, isolated user configuration, CPU affinity, probe, and blocking PTY marker instrumentation for all three paths. Each timing retained 40 launches after 5 warmups. Candidate PTY-to-probe-ready p90 was 11.675 ms, 1.534 ms below the positional wrapper's 13.209 ms p90 and within the fixed +1 ms regression gate. Probe-exit-to-editable-prompt p90 was 0.851 ms, compared with 514.209 ms for the current wrapper in this fixture because the current wrapper initialized a second interactive shell.

The dormant adapter remained within its ordinary-startup gate. Interleaved managed first-editable p90 changed from 29.872 ms to 30.297 ms, a 0.425 ms increase under the fixed +0.5 ms limit. Process tracing observed one Zsh execution on the accepted path and two on the current wrapper. The accepted path otherwise starts only the manager, existing per-session runtime and Git scan, and requested application.

The [retained report](benchmarks/foreground-startup-2026-09-03/report.md) contains the exact gates, raw samples, process traces, source identities, and reproduction commands.

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

## A native foreground-job transition protocol is deferred

The smallest plausible shell-owned contract identifies one shell-local job generation and process group, then emits ordered `started`, `stopped`, `continued`, and `finished` transitions. `finished` carries the exit or signal status after the shell has observed job completion. A new generation prevents process-group reuse from reviving old metadata. Consumers map that ephemeral job to their own application identity; the process group itself is not a provider thread, pane identity, durable route, or security authority.

Ordinary `preexec` and `precmd` hooks can bracket a simple foreground command, but they do not expose every transition at the point where Zsh assigns the foreground process group or updates its job table. A precise contract may require a small Zsh module or paired Zsh change. That cost is unjustified while Wakterm's cached process identity passes the reproducer.

The Wakterm transition and process-shape tests pass for managed start, exit, consumed Ctrl-C, stop, continue, replacement, and PID identity. The fix reuses the existing process snapshot and adds no watcher, child process, prompt hook, or independent polling loop. A `wsh` contract becomes an implementation candidate only if a later case leaves a measured stale window or polling cost, or a shell transition cannot be inferred correctly from process snapshots. An accepted result must let Wakterm remove corresponding process-lifecycle inference rather than run both owners.

## Remote and container process identities stay local to their namespace

The reproduced remote TUI is a local Codex frontend connected to a remote provider, so its local PID and start time are valid Wakterm evidence. If the frontend itself runs across SSH or inside a container, a host process tree may expose only the SSH client, container monitor, or namespace proxy. PID and process-group values are meaningful only to the process namespace that observed them.

A later event must therefore include an opaque shell-local generation and an explicit execution context when it crosses a terminal or mux boundary. The shell running in the remote or container context owns job transitions there, while Wakterm owns any mapping back to a local pane and provider session. No raw PID or process group becomes a durable cross-host identity or authorization token.

## Foreground startup remains the accepted boundary

Structured foreground startup and native OSC command reporting are accepted. Wakterm's owner-local managed-identity fix remains the solution for application identity because it passes the current fixture within the existing cache policy. Foreground-job events stay deferred behind a new reproduced correctness gap or measurable polling cost.
