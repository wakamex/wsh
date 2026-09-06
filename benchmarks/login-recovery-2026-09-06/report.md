# Login-style launches recover from unusable bundle state

Wsh now starts a system Bash recovery shell when a supported login or shell-command invocation cannot select or execute its active bundle. Missing, unreadable, malformed, incompatible, and unusable activation cases pass real execve and PTY regressions on the host and the canonical glibc 2.28 target. Ordinary healthy startup passes its fixed gate: paired p95 added latency is 0.742 ms across 50 alternating pairs, and every launch replaces the same PID with bundled Zsh.

| Healthy bare startup, identical bundle and configuration | Samples | Median | p95 |
|---|---:|---:|---:|
| Previous manager | 50 | 26.069 ms | 27.201 ms |
| Manager with login recovery | 50 | 26.171 ms | 26.857 ms |
| Paired after-minus-before overhead | 50 pairs | -0.044 ms | 0.742 ms, passing the fixed 3 ms gate |

## Reported incident and reproduced failures

An external Fedora laptop report described lost GDM and TTY access after an update and reboot with `/home/mihai/.local/bin/wsh` set as the account shell. Recovery required a boot-time root shell and changing the account back to system Bash. A fresh test account with a system-wide copy of the launcher then produced `error: no active bundle state`. The original account's activation state was not available here, so this investigation does not attribute its failure to deletion or corruption.

The retained old manager reproduces that exact error with login argv[0] `-wsh` and no arguments. It also rejects shell-command invocations such as `-wsh -c ...` as manager usage errors. The regression additionally verifies that changing the environment's state location causes recovery even while the original valid state remains intact. Wsh resolves state before user `.zshenv` can set WSH_STATE_ROOT or XDG_DATA_HOME, so differing service and terminal environments are a realistic source of missing-state behavior.

## Small pre-exec recovery boundary

The implementation recognizes leading-dash login argv[0] and raw shell flags while preserving manager command routing. Healthy launches retain Zsh login startup and direct argument forwarding. On bundle-selection or exec failure, supported common shell arguments are passed to fixed `/bin/bash --noprofile --norc` at the same identity. Recovery skips Bash startup files, strips inherited Wsh integration, clears Bash startup hooks, imported functions and option settings, and sets SHELL to `/bin/bash`. It does not choose a fallback through PATH or SHELL, change account or activation state, perform an update, or supervise a successfully executed shell.

Recovery supports `-l`, `-i`, `-s`, `-c`, their short combinations, and `--login`. Command strings and positional arguments remain opaque argv. Unknown or shell-specific flags, restricted-shell options, and script paths are rejected for recovery; Bash does not silently interpret a Zsh script. Manager failures and executed command exit statuses retain their normal meaning. [LOGIN.md](../../LOGIN.md) documents the behavior and recommends an OS-managed account shell with Wsh launched by the terminal. This recovery is development work after v0.3.1 and has not been released.

## End-to-end verification

`tests/login-shell.py` executes the real manager with overridden login argv[0], raw `-c`, combined `-lc`, and `--login -c`. It verifies missing activation, malformed JSON, old and unsupported state versions, actual permission denial, symlink state, missing bundles, changed entrypoint size, and an exec-time missing interpreter. Permission tests run unprivileged; a root test runner drops to UID 65534 for that case. Healthy Zsh starts `.zshenv`, `.zprofile`, and `.zlogin` in order, honors non-login `-c`, and returns command exit status without invoking recovery.

The PTY case reaches a recovery prompt, suspends a real sleep with Ctrl-Z, resumes it with fg, interrupts it with Ctrl-C, and runs a final command with a checked exit status. Poisoned Bash startup files, BASH_ENV, ENV, PROMPT_COMMAND, PS0, and an imported exit function cannot hijack recovery. Command arguments include spaces and non-UTF-8 bytes. Manager commands, script paths, and unsupported shell options retain errors. Existing activation bytes remain intact during a changed-environment test. The full host and canonical floor suites also verify the unchanged direct exec PID and existing foreground, plugin, profile, update, and terminal contracts.

No real account, `/etc/passwd`, `/etc/shells`, or user installation was changed. The test emulates the shell invocation boundary using real execve and a PTY; it does not run a complete GDM/PAM login or a reboot. Recovery cannot run when the launcher itself is absent or unloadable, when system Bash is unavailable, or after exec has successfully handed control to a loader or Zsh startup code that subsequently fails. These limitations are documented next to the installation guidance.

## Fixed experiment and retained identities

The [plan](plan.md) precedes implementation. The startup comparison uses the old manager built from `950bde517bdbb75d3c2a0933293b95f3d013a967` and the current local release-mode manager, with the same unsigned development bundle `ccf3c17708aae1b1fc23c4170d54ff6e78a919f0adc0e0950f3590c6325c9698`. The common fixture preserves the existing prompt and enables the three editing defaults and directory jumping. Children are pinned to CPU 0. Startup ends at native OSC 133 B; each observed PID must resolve to the exact bundled Zsh executable. No other local tool-shell invocation, build, test, or verification overlaps timing. The 50 pairs alternate order, quantiles use nearest rank, and all 100 observations are retained without retries or exclusions.

The [metadata](metadata.json) records the source base plus dirty implementation identities, native binary hashes, fixture, commands, host, and separate canonical manager and bundle identities. `implementation.tar.gz` preserves every measured implementation input. The host comparison bundle and canonical test bundle manifests retain pinned Zsh source, patches, target, toolchain, build profile, and payload digests. Both are unsigned development artifacts. Correctness, baseline failures, compressed complete suite logs, raw startup samples, host observations, and the summary remain beside this report.

Run `python3 tests/login-shell.py MANAGER BUNDLE` for the focused regression. `WSH_ZSH_ROOT=/code/wsh/build/out/zsh-cad0d67c-wsh2 ./build/test-development-bundle.zsh` ran the complete host suite; `./build/build-glibc-2.28-development-bundle.zsh` ran the canonical floor suite, including the same login regression. `python3 benchmarks/login-recovery-2026-09-06/startup.py` reproduces the fixed healthy-startup comparison with the exact managers declared in the runner. `python3 benchmarks/verify-login-recovery-evidence.py` verifies retained sources, identities, samples, arithmetic, and gates without rerunning timings.
