# Native Zsh terminal integration experiment

## Question

Can Wsh rely on the bundled Zsh's native OSC 7 and OSC 133 implementation, let Wakterm omit its duplicate prompt, output, and directory hooks, and preserve the terminal behavior Wakterm uses without adding prompt-time processes or another lifecycle owner?

## Current paths

The pinned post-5.9 Zsh revision contains upstream native terminal integration. It emits OSC 133 prompt and command-output markers and OSC 7 working-directory reports from the ZLE and command-loop implementation. These features are enabled by default and can be controlled through `.term.extensions`.

Wakterm also installs `assets/shell-integration/wakterm.sh`. Its Zsh path wraps `PS1` and `PS2`, registers `precmd` and `preexec` functions, emits a second OSC 7 report, and invokes `wakterm set-working-directory` once per prompt when the command is available. It separately publishes OSC 1337 user variables. The user-variable path is not replaced by native Zsh and remains outside the one-factor lifecycle comparison.

## Baseline and cheapest counterfactual

Run the exact bundled Zsh in a PTY with isolated startup files under three configurations:

1. Native Zsh integration alone.
2. Native Zsh plus Wakterm's current semantic-zone and directory integration, with user variables disabled.
3. Native Zsh plus Wakterm's script after it is told that the shell already owns standard terminal integration, again with user variables disabled.

Exercise a successful command, a failing command, a directory change, empty input, Ctrl-C while editing, a multiline command, output without a trailing newline, and a user `precmd` and `preexec` hook. Capture the raw byte stream and parse it with Wakterm's authoritative escape parser or terminal implementation.

The smallest intervention is a producer capability set before Zsh startup. Wakterm's injected script uses it only to omit its semantic-zone and OSC 7 sections. It does not identify terminal brands, change arbitrary Zsh behavior, or disable OSC 1337 metadata.

## Correctness gates

- Native Zsh alone produces one coherent prompt and command-output lifecycle for every accepted command and reports the changed directory through OSC 7.
- Wakterm's parser accepts the exact native byte stream and produces the same prompt, input, and output semantic zones needed by prompt navigation and output selection.
- The accepted coexistence path produces no duplicate OSC 7 or OSC 133 lifecycle and preserves pre-existing hooks once in their original order.
- Empty input and Ctrl-C while editing do not create a false executed-command region.
- A command that consumes Ctrl-C remains in the running output region until it actually returns.
- The current exit-status behavior is recorded separately. A missing optional status does not justify a Zsh source patch unless a concrete Wakterm behavior consumes it.
- Disabling native integration through `.term.extensions` remains possible and does not cause Wakterm to assume that markers exist.

## Performance and process gates

Measure 5 warmups and 40 retained runs of 100 no-op commands for native-only, duplicate, and accepted coexistence paths in interleaved forward and reverse order on one fixed CPU. The accepted path must add no prompt-time child process over native Zsh and must not regress prompt-cycle p90 by more than 0.5 ms relative to native-only. Trace process creation separately with `strace -ff -e trace=process`.

The duplicate baseline is expected to demonstrate the current avoidable cost. It is not an acceptance control for adding new Wsh work.

## Foreground-job follow-up

After the command-boundary path passes, run Wakterm's managed-frontend reproducer across exit, a consumed Ctrl-C, stop, continue, replacement, and PID reuse. Keep Wakterm's existing PID and start-time snapshot fix if it produces no stale or prematurely cleared binding within its existing 300 ms cache policy.

Only a remaining reproduced ambiguity or measurable polling cost can justify native job-transition reporting. Any native change must first be a small patch against the pinned Zsh source, use a backward-compatible OSC 133 extension or a separately proposed semantic marker, avoid publishing command text by default, and pass upstream Zsh tests plus Wsh's job-control and terminal suites. An opaque invocation identity is preferred over a host-local PID for remote and container sessions.

## First-job startup follow-up

The existing exact-argument startup path remains a launcher counterfactual. Verify whether its first application appears inside the same native OSC lifecycle as an ordinarily typed command. If it does not, compare the current one-shot `precmd` adapter with the smallest Zsh command-loop change that executes an exact argument vector before the first editable prompt. Carry a source patch only if the native path fixes the reproduced reporting gap or another correctness failure and remains proportionate to its maintenance cost.

## Limits

Allow two implementation attempts and 180 minutes for each distinct gate. After two failed changes, audit the premise before adding a module, resident supervisor, private terminal protocol, or general event bus.
