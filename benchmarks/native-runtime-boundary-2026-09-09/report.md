# Keep the C runtime in one helper per shell

The helper boundary is the simpler passing implementation. A native probe using the same C collector loses Git child ownership to Zsh's SIGCHLD handler: only 4 of 100 collections succeed in the final module run, while the standalone helper succeeds in all 100. Disabling that handler makes all 100 collections succeed but hangs an ordinary shell `wait`. The measured helper round trip is 11.850 microseconds at p95 over 1,000 requests.

| Comparison | Result | Consequence |
|---|---|---|
| Direct C collector in actual pinned Zsh, normal SIGCHLD handling | 4/100 successful collections; 96 child-wait errors | Reject direct embedding |
| Same module and workload, Zsh SIGCHLD handler suppressed | 100/100 successful collections | Confirms competing child reaping as the cause |
| Ordinary background `sleep .03` followed by `wait`, normal handler | Completes with status zero | Native shell control passes |
| Same background-job wait, handler suppressed | Still blocked at the 3-second deadline | Reject handler suppression as a product intervention |
| Same C collector in its standalone helper | 100/100 successful collections in each matched control | Retain the passing child owner |
| Helper ping, no Git, CPU 0 | 10.780 microseconds median; 11.850 microseconds p95 | IPC is small in this workload |

## Mechanism and scope

The pinned Zsh handler calls `wait3` or `waitpid(-1)` for child state changes. The collector separately calls `waitpid` for its Git PID. Once Zsh reaps that process, the collector cannot recover its exit status. The initial probe had 97 failures and the final matched binary had 96; both runs are retained. The suppression control changes only signal ownership in a disposable shell process.

The probe loads the unchanged C collector through a private module, starts its worker, and lets Zsh continue interpreting builtins while polling completion. It refuses unloading while active and joins before freeing request state. It does not install prompt rendering, manipulate the live user's shell, or claim an accepted in-process runtime. The standalone collector/renderer/helper already passed sanitizer and shell contracts in [stage 6](../native-render-2026-09-08/runtime-report.md). The module also completes the 100-request probe under ASan/UBSan without diagnostics. That whole-Zsh build retains its previously documented leak-check and function-call sanitizer exceptions; the module itself uses full address/undefined checks. This rejected module did not proceed to a full editor qualification.

An in-process replacement remains possible, but it would need coordinated child registration and exit-status delivery instead of two independent waiters. It would also need immutable request environment data: the current collector reads `PATH` and `environ` in a worker, while an interactive shell can change them. Parsing, allocation failures and blocked filesystem operations would then share the shell's failure domain. Those changes remove the helper process but add responsibilities that the current helper contains naturally.

The measured cost does not justify that machinery now. The helper's previous total added-memory workload passed at 713 KiB p90, and current IPC takes about 12 microseconds p95. Keep one cancellable C helper per shell, with prompt rendering and lifecycle local. Reopen an in-process design only when an actual multi-pane memory or latency requirement makes those savings material; rerun child ownership, environment changes, editor responsiveness, cancellation and failure-containment tests at that point. Cross-shell sharing remains a distinct deferred experiment.

## Measurement and reproduction

The IPC measurement retains 1,000 requests after one warmup. The client pre-encodes each ping, measures write/flush/read, then validates the real response outside the clock. Client and helper share CPU 0. No Git or editor work enters the interval, no builds or tests overlap it, and a separately measured empty clock has 120 ns p95 cost. This bounds the combined client I/O, pipe exchange and helper JSON work; it is not a pure serialization or editor-latency measurement.

`native/build-collector-module.zsh CONFIGURED_ZSH_SOURCE OUTPUT` builds the private module against generated headers from the matching pinned Zsh source. `native/test-collector-module.py ZSH MODULE HELPER OUTPUT` runs the ownership comparison; setting `WSH_PROBE_NO_SIGCHLD=1` selects the diagnostic suppression. `native/test-collector-jobs.py ZSH MODULE OUTPUT_JSON` retains the rejected wait behavior. `native/measure-runtime-ipc.py HELPER OUTPUT_JSON` records round trips.

The retained source archive contains the probe, harnesses, collector, matching generated Zsh headers and child-handler source. Metadata binds source, executables, the native installation, commands and toolchains. This decision preserves the tested helper protocol; it removes no supported runtime or migration code prematurely.
