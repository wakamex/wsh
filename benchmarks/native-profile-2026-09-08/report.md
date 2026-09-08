# Native profile invocation and saved reports pass

Native Wsh can now start a profile and recover its report without invoking the Rust manager. On 100 alternating traced/untraced pairs per prompt, default profiling adds 2.301 ms paired p90 with the existing prompt and 2.563 ms with Minimal, both below the existing 3 ms gate. The C reporter reproduces the Rust reporter's substantive output on the same real saved trace. Attribution, privacy, storage, hostile-input and sanitizer tests pass.

| Measurement | Observed | Predeclared gate or interpretation |
|---|---:|---|
| Existing prompt, default profile first-editable overhead, 100 pairs | 2.301 ms paired p90 | At most 3 ms, pass |
| Minimal prompt, default profile first-editable overhead, 100 pairs | 2.563 ms paired p90 | At most 3 ms, pass |
| Runtime trace readiness overhead, 60 pairs | 1.113 ms p90 | At most 3 ms, pass |
| Worst clean/dirty/untracked runtime refresh overhead, 20 pairs per state | 0.159 ms p90 | At most 0.5 ms, pass |
| Unprofiled existing prompt versus prior native build, 50 pairs | +0.921 ms paired p95 | At most +3 ms, pass |
| Unprofiled Minimal prompt versus prior native build, 50 pairs | +0.965 ms paired p95 | At most +3 ms, pass |
| Optional function profiling, Minimal, 100 pairs | 3.116 ms paired p90 | Separately measured opt-in mode; exceeds the default-mode 3 ms threshold |
| Native executable size | 982,136 bytes, +85,808 bytes | Includes system Jansson linkage and native tool code |
| Required system Jansson shared library | 66,088 bytes | Additional OS-managed dependency; package/floor qualification remains pending |

## Implementation and remaining lifecycle work

`native/profile.c` owns invocation, private storage, argument forwarding and normal-exit reporting. `native/profile-report.c` owns bounded private-file reading, schema validation and output. Together they contain 507 lines, compared with the existing 642-line Rust profile implementation. The existing 115-line Zsh profile adapter remains unchanged in this slice, as do the Rust runtime and trace protocol. The Rust manager remains available for current production consumers; no deletion is claimed before their migration.

The report uses the system Jansson decoder with duplicate-key rejection and UTF-8 validation. Native metadata records compiled identity independently of activation state. Legacy reports can be recovered even when their original bundle is absent; output explicitly describes recorded identity and does not claim to verify installed resources. Existing command statuses and raw Zsh argument bytes are preserved. Ordinary invocations create no profile state.

Stage 4 is still in progress. Native startup currently calls the existing shell instrumentation. Its editor milestone is correctly labelled as the Wsh ZLE initialization hook; the external benchmark separately observes primary OSC 133 B after all line-init hooks. Noninteractive or early-exit sessions can leave shell-buffered spans unflushed, although the new native exit reporter runs. The next bounded experiment must replace those trace-only shell calls and test lifecycle recovery before accepting stage 4 as complete.

Jansson accepts signed 64-bit JSON integers. This reader rejects larger numeric values, whereas the legacy Rust event decoder permits unsigned 64-bit counters. Real retained traces are in the common range; this experiment does not establish full unsigned-range protocol parity. Reassess the numeric contract before porting the runtime request interface in stage 5.

## Verification

The final normal build passes 75 upstream scripts with zero failures and two upstream skips. It passes 18 startup/relocation cases, nine Wsh integration suites, and the separate complete prompt-ownership fixture including four native-profile modes against real Oh My Zsh. Native profiling tests inject startup, function and editor delays, check actual runtime spans and live report recovery, preserve configuration hashes, verify private modes and exclusion of test secrets/commands/repository paths, and compare non-UTF-8 argv output against ordinary native Zsh. Nine storage/status cases cover relative paths, existing parent modes, inaccessible storage, symlinks, exit codes and SIGTERM parity.

The saved-report suite passes 45 cases, including duplicate and unknown keys, malformed and truncated JSON, schema overflow, invalid UTF-8, terminal controls, file/line limits, FIFOs, symlinks and identity mismatch. The standalone C decoder passes strict warnings and full ASan/UBSan checks, including 10,000 deterministic mutated and arbitrary byte inputs. Whole-Zsh profiling and storage tests also pass ASan/UBSan with leak detection disabled and the previously established upstream function-pointer-cast check excluded. Standalone checks have neither exclusion. The 200 ms delayed-editor observer regression passes on the final native candidate.

## Method and retained failures

The [plan](plan.md) fixes workloads, sample counts, limits and attempt bounds before implementation. Timing runs are sequential on CPU 0, with no concurrent build or VM work. Profile samples use the same binary, configuration and primary native editable marker in both modes. Runtime tracing uses the unchanged clean/dirty/untracked workload. Unprofiled comparison uses the accepted stage-2 native executable with candidate modules, functions and runtime copied into a separate control tree; original artifacts remain unchanged. Optional function profiling is a separate run.

Retained failures include an initial validator that rejected digits in field names such as `bundle_sha256`, rejection of a relative state root, and acceptance of invalid UTF-8 in function-profile text. Each has a passing regression. Two fixture errors are also retained: the editor-delay fixture needed to load ZLE before registering its hook, and the directory-mode fixture initially ignored the host umask. Neither required changing shell semantics.

[metadata.json](metadata.json) records the source revision, native lock, bundle, executable/runtime/library hashes, host and commands. `inputs.tar.gz` retains source, tests, decoder headers and standalone harnesses. `results.tar.gz` retains build and sanitizer logs, failed and final cases, effective temporary configurations, real saved traces, parity output and every raw sample/summary. `manifest.json.gz` retains the development payload manifest. The verifier checks snapshots, identities, results and gate arithmetic and runs from the shared evidence entrypoint. These are unsigned local development artifacts. No system package with the new library dependency, glibc-floor build, release or publication was exercised in this slice.
