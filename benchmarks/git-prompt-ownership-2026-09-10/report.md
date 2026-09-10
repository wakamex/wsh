# Git prompt ownership

Recognized `git-prompt` hooks now stop running when Wsh owns the prompt. Real upstream collection tests in a Git repository record zero external collector invocations under Wsh ownership and six calls when existing, failed-theme or modified implementations retain their hooks. The isolated plugin startup fixture improves from 42.320 ms to 18.681 ms median under Wsh's minimal prompt, while the existing prompt passes the 3 ms overhead gate. Each timing comparison uses 50 alternating pairs and the same plugin source.

| Prompt owner | Baseline median readiness | Candidate median readiness | Paired p95 change | Gate |
|---|---:|---:|---:|---|
| Existing prompt, external collector retained | 40.815 ms | 40.619 ms | +0.800 ms | <= +3 ms, pass |
| Wsh minimal prompt, external collector hooks removed | 42.320 ms | 18.681 ms | -23.301 ms | <= +3 ms, pass |

## Baseline and gate

Baseline `1f9c258` replaces the displayed prompt while the unmodified OMZ git-prompt plugin retains its `precmd`, `preexec` and `chpwd` hooks. The user's configuration reproduces duplicate Python/Git collection even though Wsh owns the display. The smallest intervention is removal of exactly these three recognized hooks after successful Wsh prompt activation. Existing prompts and failed Wsh theme startup must retain their hooks.

Before testing, require exact upstream plugin and collector bytes and loaded function provenance, preserve modified code and unrelated hooks, and show zero external collector invocations across first prompt, command execution and directory changes under Wsh ownership. Existing and failed-theme modes must continue collecting. Use real upstream code with an observing Python launcher. Bound paired startup p95 overhead to 3 ms using the existing 50-pair harness. Two failed interventions at a gate require a new hypothesis.

## Verification and reproduction

All seven focused cases pass on the host and on glibc 2.28: Wsh ownership, existing ownership, failed theme startup, modified plugin, modified collector, overridden hook and absent plugin. They execute the unchanged upstream Python collector through an observing launcher, create a real Git repository, exercise first prompt, command execution and directory changes, and preserve an unrelated user hook. All nine host installation contracts pass, including real OMZ coexistence. The host upstream Zsh suite reports 75 successful scripts, zero failures and two skips.

The user's actual `.zshrc` reports `wsh` Git prompt ownership with all three external hooks absent. Regular Zsh retains all three hooks. Highlighting regions, completion and Ctrl-C still pass, and startup-file hashes are unchanged. Private traces remain under `/var/tmp/wsh-git-prompt/user`.

Run `python3 native/test-git-prompt-ownership.py INSTALLATION OUTPUT` and `python3 native/measure-git-prompt-ownership.py BASELINE_INSTALLATION CANDIDATE_INSTALLATION OUTPUT`. `tests/prompt-ownership.zsh` includes the focused regression, so the canonical installation suite runs it too. Startup measurements use tracing off, CPU 0 and native OSC 133 B readiness. The timing fixture isolates this plugin outside a Git repository; the collector correctness cases run inside a repository.

`identity.json` retains the source, compiler, target, build command and native executable identities. `evidence.tar.gz` includes raw samples, summaries, real collector transcripts, installed contract logs and upstream build output. The glibc 2.28 component test uses the previously qualified native executable with the current integration and reference files overlaid in an isolated fixture; this change does not rebuild or requalify an RPM. C implementation and sanitizer qualification are unchanged. All artifacts are unsigned development artifacts.
