# Persistent history defaults

Fresh interactive Wsh sessions now retain commands across logins without requiring `.zshrc` setup. The implementation passed 32 real-PTY history checks, the complete installed glibc 2.28 suite and the upstream Zsh suite. Thirty alternating timing pairs passed the fixed overhead limits after an unchanged-binary control exposed an editing-time measurement problem.

## Behavior and correctness

| Check | Result |
| --- | --- |
| Fresh interactive login | `HISTFILE=$HOME/.zsh_history`, `HISTSIZE=10000`, `SAVEHIST=10000`, incremental saving on and live sharing off |
| Persistence | Commands appear in the history file before exit and in a subsequent login; commands from both concurrent sessions survive an abrupt termination |
| Session navigation | Already-open sessions do not automatically import each other's new commands |
| User policy | Environment and startup-file paths, limits, zero/empty/unset opt-outs, exit-only saving, timed saving and explicit sharing remain effective |
| Actual Oh My Zsh | Existing 50,000-entry memory limit, 10,000-entry saved limit and sharing policy remain effective; saving works |
| Storage | New history files are private, configured retention is enforced on exit and no startup configuration is generated |
| Zsh modes | Noninteractive invocations and `-f` retain the underlying Zsh history defaults |
| Installed regression suite | Complete shared suite passes, including editing, completion, ownership, profiling, recovery, foreground jobs and helper lifecycle/protocol cases |
| Upstream and source checks | 75 upstream scripts pass, zero fail and two skip; `tests/verify-current.zsh` passes |

The 30 self-contained history checks now run in the shared installed suite. Two additional checks exercise the real Oh My Zsh checkout through `WSH_TEST_OMZ`. This qualification uses PTY login-style processes and the canonical build container; no new Fedora RPM, COPR build, PAM/GDM login or reboot test was run for this change.

## Timing

| Measurement, 30 alternating pairs | Baseline p90 | Candidate p90 | Paired p90 overhead | Fixed maximum overhead |
| --- | ---: | ---: | ---: | ---: |
| Empty-home launch to editable prompt | 23.330 ms | 23.856 ms | 1.876 ms | 3 ms |
| Enter to editable prompt after editing settles | 1.787 ms | 2.023 ms | 0.401 ms | 1 ms |

These timings compare persistence enabled with the previous unconfigured behavior in fresh homes. They do not measure loading a large existing history. The overhead column is the p90 of individual candidate-minus-baseline pairs, not the difference between the two marginal p90 values.

The initial command timer included typing and redraw of the sentinel command. It failed with 1.549 ms paired p90 overhead even though the candidate's marginal p90 was lower. Running the unchanged baseline against itself also failed, with 1.508 ms of apparent overhead. That control falsified the measurement's ability to distinguish a 1 ms history cost from editing variation.

The corrected boundary types the same command before the timer, waits for 50 ms of terminal-output quiet, then measures Enter through native OSC 133 B. Its unchanged-binary control passed with 0.596 ms paired p90 overhead. The candidate then passed on its first corrected run. No implementation change or threshold increase was made in response to timing. All four runs and both harness versions are retained.

## Implementation and failed checks

The unchanged native binary fails the new test at the fresh-default assertion: no history file is configured and saving is disabled. Ordinary Zsh history parameters and options are the smallest counterfactual, so Wsh supplies those defaults before system and user startup files and leaves Zsh responsible for storage and retention.

The first implementation passed the persistence and override cases but failed timed saving: Zsh requires `INC_APPEND_HISTORY` to be off for `INC_APPEND_HISTORY_TIME` to take effect. The final implementation yields its incremental-saving default when startup configuration selects timed saving or sharing. This was a Wsh default-policy interaction, not an upstream Zsh bug.

The first complete-suite run also caught an outdated profiling assertion: it classified every `.zsh*` file, including the newly created `.zsh_history`, as startup configuration. That test now hashes the five actual startup filenames, preserving its configuration-integrity check. The complete suite passed after that test correction.

## Identity and reproduction

Both installations are unsigned local development artifacts using GCC 8.5.0, target `x86_64-redhat-linux`, the same container SDK and Zsh revision `cad0d67c76e2be7371cf3526b79ea2581810d35a`. The baseline installation's native-source lock equals the pre-change `e93326259c6255b8497008ea33a12eaa366b682b` tree. The candidate changes only the startup policy among compiled native inputs. Tracing is off; both use the Minimal prompt, the same built-in editing features and identical synthetic commands and fresh-home fixtures. Timing instrumentation is external PTY observation in both variants, with its null-comparison behavior recorded above.

[Identity and raw samples](identity.json) record the host, compiler-container identity, source hashes, binary identities and all accepted timing rows. The [evidence archive](evidence.tar.gz) contains full installation manifests, source inputs and patch, the predeclared gate, baseline and intermediate failures, upstream and installed logs, synthetic PTY transcripts and all timing runs. Its `SHA256SUMS` covers the retained files. No shell binaries or personal history are included.

Build and full installed-suite commands:

```sh
podman run --rm --init --userns=keep-id --network=none \
  --volume /code/wsh:/workspace:z --workdir /workspace \
  --env LANG=C --env LC_ALL=C --env TZ=UTC \
  --env WSH_BUILD_JOBS=4 --env WSH_KEEP_FAILED_BUILD=1 \
  --env WSH_ZSH_OUTPUT_ROOT=/workspace/build/portable/history-defaults-final/zsh \
  --env WSH_BUNDLE_OUTPUT_ROOT=/workspace/build/portable/history-defaults-final/bundles \
  localhost/wsh-native-builder:e1fdf68370077c882beeaa4b \
  zsh -df build/build-native-installation.zsh

podman run --rm --init --userns=keep-id --network=none \
  --volume /code/wsh:/workspace:z --workdir /workspace \
  --env LANG=C --env LC_ALL=C --env TZ=UTC \
  localhost/wsh-native-builder:e1fdf68370077c882beeaa4b \
  zsh -df build/check-native-installation.zsh \
  /workspace/build/portable/history-defaults-final/bundles/07c5c12c8bf31b0f8575355dbc435590d66256540fc5721c88bcda0292c2ace6 \
  /workspace/build/portable/fedora-layout/reference/zsh-cad0d67c-wsh2 \
  /workspace/build/portable/history-defaults-final/checks-complete
```

Host history and timing commands, run from `/code/wsh`:

```sh
history_before=build/portable/fedora-layout/bundles/7241bb10b64ea4507965dc25a49bc13689b6254c6fc2e78217661abf4465e2dd/bin/wsh
history_after=build/portable/history-defaults-final/bundles/07c5c12c8bf31b0f8575355dbc435590d66256540fc5721c88bcda0292c2ace6/bin/wsh
TMPDIR=/var/tmp WSH_TEST_OMZ=/home/mihai/.oh-my-zsh \
  python3 tests/history-persistence.py "$history_after" /var/tmp/wsh-history-final-check
TMPDIR=/var/tmp python3 benchmarks/history-defaults-2026-09-15/measure.py \
  "$history_before" "$history_before" /var/tmp/wsh-history-enter-control
TMPDIR=/var/tmp python3 benchmarks/history-defaults-2026-09-15/measure.py \
  "$history_before" "$history_after" /var/tmp/wsh-history-enter-final
env -u FPATH TMPDIR=/var/tmp TMPPREFIX=/var/tmp/wsh-history-current \
  zsh -df tests/verify-current.zsh
```
