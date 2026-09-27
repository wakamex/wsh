# Native pane history with merge-on-exit

Wsh now recalls the current pane's commands ahead of shared history and merges new commands into shared history on exit. Real PTY tests passed 38 history checks, including crash recovery, nesting, opt-outs and the actual Wakterm adapter. The complete installed suite and upstream Zsh tests passed. In the controlled empty-home comparison, paired p90 overhead was 1.186 ms at startup and 0.330 ms from Enter to the next editable prompt.

## Behavior and validation

| Case | Result |
| --- | --- |
| Two live panes | Each journals its own commands; neither imports the other's new commands or publishes its own to shared history before exit |
| Restarted pane | Loads shared history, then its retained pane history, so recent pane commands appear first during backward recall |
| Normal exit | Merges pending commands into the shared file and the pane file using Zsh parsing, locking and retention |
| SIGKILL and exec | A subsequent shell with the same token recovers the pending journal |
| Nested shells | Use the original shared path, including an explicitly exported custom `HISTFILE`; they do not write to the outer shell's pane file |
| Duplicate live token | A process lock admits one pane owner; the other shell keeps ordinary history |
| Opt-outs and contexts | Empty/unset `HISTFILE`, zero `SAVEHIST`, terminal opt-out, invalid token, pre-existing history context, scripts and `-f` prevent activation; a memory-only `fc -p` context does not enter pane or shared files |
| Storage failures | An unavailable state directory falls back to ordinary history; a symlink journal is rejected; a failed shared merge retains pending commands and retries on a later start |
| Retention and permissions | Configured limits bound pane and shared files; native files are private; timed incremental saving remains effective |
| Oh My Zsh and Wakterm | OMZ history works with pane policy; the real terminal adapter skips its own pane owner when Wsh claims it |
| Existing behavior | All 32 ordinary-history checks, including actual OMZ, pass; the full installed suite passes, with 35 self-contained pane checks included |
| Build and source checks | 75 upstream scripts pass, zero fail and two skip; current-source contracts and `git diff --check` pass |

These are local unsigned development builds. No package, release or deployment was changed. A real Wakterm mux restart with the matching deployed builds remains the integration gate. The PTY test supplies and restores the same token directly.

## Storage and ownership decisions

The terminal supplies a canonical lowercase UUID in `WAKTERM_PANE_TOKEN`. Wsh uses `${XDG_STATE_HOME:-$HOME/.local/state}/wsh/history/panes/<uuid>.zsh`, a `.pending` journal and a `.owner` lock. A validated UUID is already a safe single filename component, so hashing would add no benefit here. Wsh owns its own files; generic Bash/Zsh adapter files are separate.

`HISTFILE` remains unchanged. Wsh redirects automatic saves only in the original owning history context. This preserves inherited custom shared paths and lets native Zsh history contexts control private recall. Wsh claims `WSH_NATIVE_PANE_HISTORY=1` before startup adapters load, activates after the shared history has loaded, and clears the claim if activation is inapplicable or unavailable. That capability is not exported. The exported `WAKTERM_PANE_HISTORY_OWNER` PID preserves outermost ownership across nested shells and permits `exec` replacement.

Pane mode deliberately disables live sharing and enables incremental journal saving, retaining timed saving when selected. `WAKTERM_SHELL_SKIP_PANE_HISTORY=1` keeps ordinary user policy. Pending data is removed only after both destination merges succeed. Interruption between those writes can replay entries. Unused pane files are not automatically removed. A new privacy command, third-party collector control, garbage collection or exactly-once transaction machinery is outside this change.

## Measured cost

| Measurement, 30 alternating pairs on CPU 11 | Previous default p90 | Native pane mode p90 | Paired p90 overhead | Predeclared maximum |
| --- | ---: | ---: | ---: | ---: |
| Fresh-home launch through editable prompt | 21.029 ms | 22.096 ms | 1.186 ms | 3 ms |
| Enter through editable prompt | 1.918 ms | 2.005 ms | 0.330 ms | 1 ms |

Both variants receive the same token and state-directory environment. The baseline ignores the token and uses the existing incremental shared-history default. Both use Minimal, the same editing features, disabled tracing and the same external PTY observer. The command is typed before timing; 50 ms of output quiet precedes Enter. Readiness is native OSC 133 B. These are empty-home costs, including creation of pane storage, rather than measurements of large retained-history loading or exit merging. The overhead column is p90 of paired differences, not the difference of marginal p90s.

The first unpinned comparison failed: paired p90 overhead was 7.914 ms startup and 3.629 ms Enter-to-prompt, while both startup marginal p90s were around 53 ms. A later unchanged-binary comparison ran around 25 ms and passed, suggesting transient host contention rather than establishing its cause. The host was concurrently running other CPU-intensive workloads. Before the controlled rerun, a one-second per-CPU sample selected idle CPU 11. Pinning the observer and descendants there gave an unchanged-binary control of 0.427 ms startup and 0.205 ms Enter overhead. The candidate then passed on its first pinned run. No implementation or thresholds changed for timing; all four runs and the CPU-selection sample are retained.

## Baseline and implementation corrections

The previous native build fails pane isolation because its incremental saves go directly to shared history. The smallest implementation keeps Zsh's storage owner and adds native save routing plus startup/exit calls. Merging temporarily pushes a Zsh history context so saved-file parsing and retention do not replace the active recall list.

The first candidate missed automatic calls that pass `HISTFILE` explicitly, so it still failed isolation. The next candidate passed the lifecycle and policy cases but failed duplicate ownership: acquiring a POSIX lock before `movefd()` lost the lock when `movefd()` closed the original descriptor. Acquiring after the move fixed the failure. All remaining cases passed in that intermediate run, and all 38 passed after the lock correction. These were Wsh integration defects; no upstream Zsh defect was confirmed.

## Wakterm adapter findings

The retained direct counterexample executes the actual `__wakterm_pane_history_merge` function against a missing shared-file parent. It writes the pane file, fails the shared append, removes `.new` and returns success. Pending data should survive any unsuccessful merge.

Code inspection also found that raw `cat` appends bypass Zsh history locking and retention; the adapter redirects an empty or unset `HISTFILE` into durable pane storage; and an exported `HISTFILE` can make a nested shell inherit the outer `.new` path even when it declines ownership. For Zsh, `zshexit` runs after the shell's normal history save, so clearing `HISTFILE` there cannot suppress the already-completed save.

When assigning a fresh pane token, Wakterm should clear an inherited `WAKTERM_PANE_HISTORY_OWNER`. The owner check is PID-only, so a mux launched from an owned shell can otherwise carry the old owner's marker into a different logical pane. Wsh's native guard intentionally follows the same marker contract; terminal-side token issuance owns that reset. Actual mux restart and fresh-pane behavior remain for Wakterm qualification.

## Reproduction and evidence

[Identity](identity.json) records the host, container, binary and source hashes, adapter identity and accepted raw timing samples. The [evidence archive](evidence.tar.gz) contains upstream and installed logs, all timing runs, synthetic PTY transcripts, intermediate implementation inputs, installation manifests, the predeclared plan and the actual adapter counterexample. `SHA256SUMS` covers its retained files. No executable bundles or personal history are archived.

The baseline native-source lock matches the pre-change `0bbb22a` tree. Both use GCC 8.5.0, target `x86_64-redhat-linux`, the same SDK and upstream Zsh revision `cad0d67c76e2be7371cf3526b79ea2581810d35a`. Build the candidate with:

```sh
podman run --rm --init --userns=keep-id --network=none \
  --volume /code/wsh:/workspace:z --workdir /workspace \
  --env LANG=C --env LC_ALL=C --env TZ=UTC \
  --env WSH_BUILD_JOBS=8 --env WSH_KEEP_FAILED_BUILD=1 \
  --env WSH_ZSH_OUTPUT_ROOT=/workspace/build/portable/pane-history-qualified/zsh \
  --env WSH_BUNDLE_OUTPUT_ROOT=/workspace/build/portable/pane-history-qualified/bundles \
  localhost/wsh-native-builder:e1fdf68370077c882beeaa4b \
  zsh -df build/build-native-installation.zsh
```

The accepted installation is `build/portable/pane-history-qualified/bundles/41c855e66cc84478444c7865e5a68d55c2857f07cb06ad6dda1e3323ad86d9f9`. Its installed checks ran in the same container with `build/check-native-installation.zsh`, the reference `build/portable/fedora-layout/reference/zsh-cad0d67c-wsh2` and output `build/portable/pane-history-qualified/checks`, each under `/workspace`.

Host checks and timing, from `/code/wsh`:

```sh
pane_before=build/portable/history-defaults-final/bundles/07c5c12c8bf31b0f8575355dbc435590d66256540fc5721c88bcda0292c2ace6/bin/wsh
pane_after=build/portable/pane-history-qualified/bundles/41c855e66cc84478444c7865e5a68d55c2857f07cb06ad6dda1e3323ad86d9f9/bin/wsh
TMPDIR=/var/tmp WSH_TEST_WAKTERM=/code/wakterm/assets/shell-integration/wakterm.sh \
  WSH_TEST_OMZ=/home/mihai/.oh-my-zsh \
  python3 tests/pane-history.py "$pane_after" /var/tmp/wsh-pane-qualified
TMPDIR=/var/tmp WSH_TEST_OMZ=/home/mihai/.oh-my-zsh \
  python3 tests/history-persistence.py "$pane_after" /var/tmp/wsh-pane-qualified-history-defaults
TMPDIR=/var/tmp taskset -c 11 python3 benchmarks/pane-history-2026-09-26/measure.py \
  "$pane_before" "$pane_before" /var/tmp/wsh-pane-timing-pinned-control
TMPDIR=/var/tmp taskset -c 11 python3 benchmarks/pane-history-2026-09-26/measure.py \
  "$pane_before" "$pane_after" /var/tmp/wsh-pane-timing-pinned
env -u FPATH PATH=/usr/bin:/bin:/home/linuxbrew/.linuxbrew/bin \
  TMPDIR=/var/tmp TMPPREFIX=/var/tmp/wsh-pane-check zsh -df tests/verify-current.zsh
```

The source check uses the system Python with PyYAML. The Homebrew Python selected by the default tool PATH lacks that dependency.
