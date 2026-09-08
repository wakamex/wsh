# Native startup traces survive early and noninteractive exit

Native startup profiling now retains spans when `.zshenv` exits early or a noninteractive command exits, execs another program, or receives a fatal signal after startup. Previously both normal noninteractive exit and early `.zshenv` exit saved only the launch event. Eleven real-shell lifecycle cases pass in normal and sanitized builds. Default profiling remains below its 3 ms paired p90 overhead gate on 100 alternating pairs per prompt.

| Measurement | Observed | Fixed gate |
|---|---:|---|
| Existing prompt, default profile first-editable overhead, 100 pairs | 2.090 ms paired p90 | At most 3 ms, pass |
| Minimal prompt, default profile first-editable overhead, 100 pairs | 2.225 ms paired p90 | At most 3 ms, pass |
| Unprofiled existing prompt versus preceding native build, 50 matched pairs | +0.522 ms paired p95 | At most +3 ms, pass |
| Unprofiled Minimal prompt versus preceding native build, 50 matched pairs | +0.410 ms paired p95 | At most +3 ms, pass |

## Ownership and recovery

Fixed startup events now record timestamps directly in a bounded C array instead of evaluating a shell function through `execstring`. The buffer holds at most 32 events and performs no allocation, formatting or I/O while recording. Native startup flushes the records once after startup; normal early exit flushes remaining records before the existing native report callback. Forked children cannot flush the parent's records. Missing optional integration and `-f` still produce the native entry milestone.

The report uses `native-startup-enter` when available and accepts earlier native traces with the previous adapter milestone. Interrupted startup records its start without inventing an end or a completed duration. A process killed or replaced before reaching a flush point can still lose that buffered prefix. Saved-report recovery after completed startup is tested for exec, SIGKILL and SIGTERM; arbitrary power-loss durability is outside this profile format.

The existing shell adapter still owns optional function profiling, component callbacks and the initial ZLE callback. Runtime collection and tracing are unchanged. Their previously accepted runtime timing evidence remains applicable. This change adds no shared service, module export or dependency. It is an independently accepted startup correction; remaining profile inheritance and broader lifecycle ownership are reviewed before closing stage 4.

## Verification and evidence

The candidate passes 75 upstream scripts with zero failures and two upstream skips, 18 startup cases, nine Wsh contract suites including real OMZ profile modes, all 45 saved-reader boundaries, and the existing profile/storage suites. The new lifecycle test covers three early startup exits, full login-file delays, subshell isolation, noninteractive status, exec, SIGKILL, SIGTERM, `-f` and a relocated executable without Wsh integration. The normal and scoped whole-Zsh ASan/UBSan builds pass those cases. A standalone strict-warning/full-ASan/UBSan harness exercises 10,000 timestamp calls and rejects FIFO, symlink and non-private trace replacements without blocking or writing them. The external primary OSC 133 B observer still includes the injected 200 ms late editor hook.

Timing uses sequential CPU-0 runs after correctness, with the predeclared sample counts and no concurrent build or VM activity. The first unprofiled run is retained as diagnostic evidence because three files contained differing compiled installation paths. The accepted repeat uses a copied control with candidate `_run-help`, `run-help` and `zsh/newuser.so`; all resources and the runtime then match while the native executable differs. Original bundles remain unchanged. A test-fixture directory-name collision was fixed before the final lifecycle runs; its failed sanitizer log is retained.

[metadata.json](metadata.json) identifies source, locks, compiled binary, helper, matched resource hashes, host and commands. `inputs.tar.gz` preserves implementation/tests and the standalone harness; `results.tar.gz` contains the baseline reproductions, final and failed logs, configurations, traces, raw timing and summaries; `manifest.json.gz` contains the candidate development manifest. The shared retained-evidence verifier checks these identities and recomputes the timing gates. All artifacts are unsigned local development builds. Package, glibc-floor and publication checks remain separate migration work.
