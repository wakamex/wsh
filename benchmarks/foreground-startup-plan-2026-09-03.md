# Structured foreground startup experiment

## Question and current failure

Can Wsh start an exact argument vector as the first foreground job of a normal interactive shell, preserve Zsh job control across interrupt and suspension, and return to one editable prompt without material startup cost?

Wakterm commit `4ad5fdf4860847f594b4c310a264ae9856c25b20` reconstructs a restored provider command as quoted shell source and invokes `shell -l -i -c '<command>; exec "$0" -l'`. The current pure unit fixture covers one argument containing spaces. Source inspection establishes that a non-UTF-8 Unix argument is rejected before launch. A direct PTY probe against Zsh 5.9 reproduced the suspension failure: Ctrl-Z stopped the provider, the wrapper replaced itself with a new shell, and `fg` returned `fg: no current job`.

The positional-argument counterfactual invokes `shell -l -i -c '"$@"; exec "$0" -l' shell <argv...>`. It removes command reconstruction and preserves Unix argument bytes, but it retains the same shell replacement after a stopped job. The PTY fixture must test that failure rather than treating argv fidelity alone as success.

## Candidate

Add `wsh run-foreground [--bundle <bundle>] [--state-root <directory>] [--login] -- <command> [arguments...]`. The launcher passes the command vector as Zsh positional parameters with `-i -s`, and the bundle startup adapter captures it before user startup can consume the parameters. A one-shot Wsh `precmd` hook executes the captured array directly, then removes its state before the first editable prompt. The same Zsh process owns the job table and the later prompt.

The first candidate uses existing Zsh hooks and arrays. It does not add a resident supervisor, serialize argv into shell source, parse user configuration, or patch Zsh. Wakterm remains responsible for choosing the command, arguments, environment, cwd, restore policy, and whether a login shell is requested. A second consumer is not required if this focused Wakterm path passes the correctness and performance gates.

## Fixed correctness gates

- Empty arguments, whitespace, quotes, newlines, wildcard characters, dollar signs, leading dashes, Unicode, and a Unix non-UTF-8 argument reach the probe byte for byte.
- The probe process group equals the terminal foreground process group while it runs and a nested child stays in that process group.
- Ctrl-C terminates a default-signal probe and produces one subsequent editable prompt.
- A probe that consumes Ctrl-C stays foreground and produces no prompt until it exits.
- Ctrl-Z stops the probe, returns the terminal to the same shell, and leaves a resumable job. `fg` resumes the same PID and process group; Ctrl-C then terminates it and returns one prompt.
- Normal exit, nonzero exit, interrupt, and suspension leave no zombie or extra shell layer.
- Terminal echo and canonical-input state match their initial values at the returned prompt.
- Login mode loads the applicable user login startup files once. Non-login mode does not add login startup files. Ordinary aliases and hooks remain present at the returned prompt.
- Twenty repeated foreground launches in fresh PTYs do not accumulate processes, stopped jobs, startup-file loads, or terminal-state changes.
- The current and positional wrappers retain their expected suspension failure in the comparison fixture so a later accidental weakening cannot erase the motivating reproducer.

## Fixed performance gates

Use the same complete development bundle, isolated user configuration, CPU affinity, probe binary, and instrumentation for every foreground variant. Record 5 warmups and 40 retained forward/reverse observations for PTY-to-probe-ready and probe-exit-to-editable-prompt latency. Run the accepted implementation through the canonical glibc 2.28 build and correctness suite separately.

The candidate selects an already activated bundle through the compact state used by an installed Wsh session. Explicit `--bundle` verification is a deliberate diagnostic path and remains outside startup timing.

Measure dormant ordinary startup with baseline and candidate builds interleaved on every repetition and a blocking read ending at the same editable-prompt marker. Separate build-wide batches cannot enforce a sub-millisecond regression gate under changing host load.

- Candidate PTY-to-probe-ready p90 may be at most 1 ms slower than the positional wrapper using the same bundled Zsh and startup configuration.
- Candidate probe-exit-to-prompt p90 may be at most 1 ms slower than the current wrapper and should avoid its second shell initialization.
- Adding the dormant startup adapter may regress ordinary managed first-editable p90 by at most 0.5 ms across 40 retained launches.
- The candidate starts no process beyond the existing Wsh launcher, one Zsh, the requested foreground job and its explicit fixture child, and the existing per-session runtime and Git scan.

Correctness takes precedence over timing. A passing latency result cannot admit a path that loses a stopped job, changes argv bytes, duplicates startup files, or leaves terminal state damaged.

## Stop limit

Allow two implementation attempts and 120 minutes. If the hook path cannot preserve both exact argv and job control, audit whether a small bundled-Zsh change is proportionate before editing Zsh. Do not add a resident supervisor, process-attachment mechanism, or general lifecycle protocol to rescue this experiment.
