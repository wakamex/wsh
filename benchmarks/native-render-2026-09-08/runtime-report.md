# Complete C helper passes correctness and resource gates

The complete C helper preserves the tested themes, Git snapshots, cancellation, native shell integration and trace recovery while reducing the helper executable from 1,679,240 bytes to 372,320 bytes. Correctness tests ran before matched collection and native-startup measurements; all fixed resource gates pass. The implementation remains an opt-in prototype for the runtime-boundary and migration comparisons.

| Workload | Observed result | Fixed limit |
|---|---:|---:|
| Git collection, six clean/dirty/untracked and fresh/reused-helper workloads | Largest paired p95 increase 0.207 ms | +3 ms |
| Native startup, existing prompt | Paired p95 increase 0.314 ms | +3 ms |
| Native startup, Minimal prompt | Paired p95 increase 0.419 ms | +3 ms |
| Added settled memory over raw Zsh plus integration, 20 sessions | 713 KiB p90; 738 KiB maximum | 4,096 KiB p90; 5,120 KiB maximum |
| Runtime tracing, three repository states | Largest readiness overhead 1.127 ms p90 | 3 ms |
| Runtime tracing, three repository states | Largest refresh overhead 0.155 ms p90 | 0.5 ms |
| Inherited Git stdout after direct child exit, sanitized helper | Cancellation/shutdown 15.409 ms; descendant removed | 1 second |

## Correctness

The final sanitized build passes 2,237 protocol-decoder cases against the actual Rust runtime, including 2,000 deterministic malformed-byte mutations, duplicate/unknown/missing fields, integer and type boundaries. Another 400 complete responses compare all four themes, repeated snapshots, full-u64 IDs and durations, signed exit-status boundaries and stale-generation rejection. The optimized final build repeats those comparisons. The earlier renderer slice supplies 45,600 exact byte comparisons and the parser slice supplies definition and upstream-parser coverage.

The real-Git matrix passes 23 cases, including linked/nested worktrees, actual operation conflicts, detached/tag states, non-UTF-8 metadata and paths, and full-width IDs. Nine malformed-metadata cases and 50 repeated cancellations end in one complete final-generation snapshot. Four real-Git output faults preserve optional-lock suppression, bounded output, timeout and protocol liveness. Both cancellation and timeout remain effective after the direct Git child exits while a descendant holds stdout.

Fifteen lifecycle cases cover a partial request while a worker completes, empty input, EOF with and without a final newline, exact and excessive line lengths, regular/private/bounded trace files, symlink/FIFO/directory rejection, buffered profile events, unchanged repaint markers, signal termination, active EOF and parent death. Live and buffered traces preserve event ordering and exclude fixture paths. All C sanitizer tests enable address and undefined-behavior checking and leak detection without exclusions.

The final comparison installation passes all nine existing native component contracts, including actual Oh My Zsh prompt coexistence and exact foreground job control. The runtime PTY suite passes isolated internal-job ownership, prompt interrupts, unchanged repaint suppression, crash fallback and shell-exit cleanup. The native core and integration resources remain identical between the two measured installations.

## Explicit protocol difference

The C helper rejects a decoded cwd containing NUL. The Rust baseline accepts that message, returns a not-a-repository snapshot and replaces the control character in its rendered prompt. A filesystem working directory cannot contain NUL. The retained boundary test records both responses; no claim of identical behavior for that input is made. This is the same C-string boundary already exposed by the collector prototype. Normal native shell callers cannot produce it.

The private profile timestamp uses an unsigned 64-bit microsecond count in C. The existing native profiler supplies a current Unix timestamp within that range; the Rust helper's environment parser also accepts larger u128 values. Saved-report parsing is unchanged in this slice.

## Ownership and maintenance comparison

One helper process still belongs to each shell. The C main thread polls stdin and an owned completion pipe; one worker handles Git discovery, process execution and parsing. One pending replacement request replaces the Rust reader thread and bounded event queue. Active collection therefore uses two helper threads instead of three. This explicitly changes internal scheduling as well as language; it is not a language-only performance claim. Stdin flags remain unchanged, and signal handlers only record termination for normal cleanup.

The helper contains the previously tested C collector, TOML validator and renderer, plus request decoding, generation ownership, output and trace handling. Its build no longer needs Rust or the temporary collector bridge. The repository still needs Rust for the retained default runtime and manager. The prototype deletes none of those supported paths yet.

The C build adds system zlib and pinned tomlc17/yyjson source. The existing TOML compatibility patches and both upstream suites remain maintenance responsibilities. Native profile reporting still links Jansson; JSON-library consolidation is a separate decision. Exact source sizes, headers, patches, executable identities and dynamic dependencies are retained in the metadata. Physical line counts are not treated as a simplification score because the files use different formatting conventions. The concrete reductions are helper threads, executable size and the runtime's Rust build boundary; adoption still requires the remaining migration and target qualification.

## Measurement and reproduction

Collection uses 50 alternating pairs in each of six workloads over a 1,000-file real repository, with 100 changed or untracked files where specified. Fresh-helper measurements begin after the ready handshake; filesystem caches are not forcibly evicted. Native startup uses 50 alternating pairs per prompt owner and observes the native primary-prompt/editor-ready markers. Memory uses the existing raw-Zsh-plus-integration workload, not total native-distribution memory. Runtime tracing uses 20 alternating pairs per state. Shells/helpers run on CPU 0 and timing stages run sequentially without concurrent builds or tests. No samples are excluded.

`native/build-runtime-prototype.zsh OUTPUT` builds the opt-in helper. Prefix it with `CC=clang CFLAGS='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer'` for sanitizers. `native/test-runtime-protocol.py RUST C OUTPUT` compares protocol and responses; `native/test-runtime-lifecycle.py C OUTPUT` verifies lifecycle behavior. Existing Git, output, PTY and native-installation harnesses accept this helper. The metadata records every command and the unsigned comparison installation identities. No package publication, live installation, account-shell change, target-floor claim or independent-build claim is included here.
