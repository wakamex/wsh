# C Git collector passes at the existing helper boundary

The C collector preserves the tested Git behavior and passes the resource gates, but this isolated port does not establish a speed or maintenance improvement. I compared complete snapshots against the corrected Rust collector on real Git repositories, ran the C path under ASan/UBSan, and measured alternating pairs with the helper boundary unchanged. The C implementation remains an opt-in prototype for the full runtime comparison.

| Workload | Rust median collection ms | C median collection ms | Paired p95 C regression ms | Gate ms |
|---|---:|---:|---:|---:|
| Clean repository, fresh helper | 8.681 | 8.663 | +0.242 | +3 |
| Clean repository, reused helper | 8.382 | 8.434 | +0.332 | +3 |
| 100 modified files, fresh helper | 3.911 | 3.924 | +0.162 | +3 |
| 100 modified files, reused helper | 3.824 | 3.854 | +0.165 | +3 |
| 100 untracked files, fresh helper | 4.225 | 4.216 | +0.154 | +3 |
| 100 untracked files, reused helper | 4.109 | 4.133 | +0.151 | +3 |

| Resource or behavior | C result | Gate or comparison |
|---|---:|---|
| Existing prompt, paired p95 first-editable regression | +0.523 ms | At most +3 ms |
| Minimal prompt, paired p95 first-editable regression | +0.513 ms | At most +3 ms |
| Inherited stdout cancellation and shutdown | 1.192 ms; descendant gone | Under 1 second, successful shutdown |
| Added retained PSS, p90 / maximum | 1,628 / 1,654 KiB | At most 4,096 / 5,120 KiB |
| Runtime trace readiness overhead, p90 | 1.102 ms | At most 3 ms |
| Runtime trace refresh overhead, worst workload p90 | 0.132 ms | At most 0.5 ms |
| Active threads during inherited stdout fixture | 3 | Same as corrected Rust |
| Helper executable size | 1,573,640 bytes | Rust 1,679,240 bytes; C additionally links system zlib |
| Collector implementation and bridge source | 607 C/header lines plus 160 Rust bridge/build lines | Rust collector 406 lines, excluding its test-module declaration |

## Correctness and failure evidence

Both feature selections pass the workspace suite. The C path passes 23 real-Git matrix cases, including unborn and detached HEAD, annotated and packed tags, non-UTF-8 paths and tag names, linked worktrees, nested repositories, actual conflicted operations, relative PATH lookup, and unsigned-64-bit maximum request IDs and generations. The relative-cwd case explicitly verifies the existing protocol rejection. The remaining cases require successful snapshots; matching errors cannot satisfy them.

The standalone C driver passes 10,015 deterministic parser and byte-mutation comparisons against the actual Rust status parser, Rust UTF-8 lossy conversion, Unicode trimming, and packed-record validation. It compiles with strict warnings and ASan/UBSan, including leak detection. The complete C collector also passes the runtime suite and real-Git matrix with ASan/UBSan and no sanitizer exclusions. Nine malformed metadata cases cover missing, invalid, NUL-containing and oversized HEAD, FIFO metadata, oversized packed records, and a cyclic tag directory. Fifty cancellations are followed by a complete final-generation snapshot with no surviving recorded Git processes. Four output-fault cases cover excessive output, invalid UTF-8, failure status and closed stdout with a running child. Inherited stdout remains cancellable and times out with descendant cleanup.

The native installation passes all nine existing component contracts, including real Oh My Zsh coexistence, prompt ownership and foreground startup. The runtime PTY suite verifies hidden helper ownership, job control, interrupt survival, repaint suppression, crash fallback and shell-exit cleanup. The Zsh core bytes are unchanged from the previously tested native installation, so this comparison does not rerun upstream Zsh tests.

The initial C matrix rejected an entire snapshot when a packed tag contained invalid UTF-8; Rust ignores that packed file while preserving the snapshot. The fix validates the complete packed stream before using its matches. A direct parser comparison then found that a temporary 32-byte numeric buffer discarded valid counters with many leading zeroes. Checked digit accumulation removes that limit while preserving u64 overflow behavior. Both failures and their source bytes are retained. An initial relative-path fixture exercised protocol rejection rather than executable lookup; the corrected fixture requires a successful snapshot using an absolute cwd and a relative-only PATH entry.

## Scope and implementation cost

The optional `native-git` Cargo feature selects the C collector inside the existing Rust worker. Rust still owns request parsing, themes, rendering, generation publication and helper lifecycle. The typed bridge preserves the full u64 protocol range without adding JSON conversion or a second helper. C owns discovery, tag resolution, process execution, bounded stdout, status parsing and snapshot fields. It uses libc and system zlib. The child prepares no allocated state after fork; parent-death arguments follow the documented [prctl argument-width contract](https://man7.org/linux/man-pages/man2/prctl.2.html).

The new bounds are explicit prototype differences: individual metadata records and paths are limited to 64 KiB, packed refs stream one bounded line at a time, metadata must be regular files, and embedded NUL metadata is ignored. Existing limits remain 4 MiB for status output and 1 MiB for a decompressed loose tag object. Cancellation and the two-second request deadline are checked between filesystem operations, including metadata traversal; a kernel filesystem call that itself blocks remains outside the local-filesystem qualification. Allocation failure terminates the optional helper, matching Rust allocation failure containment.

The C/header source has 201 more lines than the Rust collector before counting the temporary bridge. The executable shrinks by 105,600 bytes, but system zlib replaces statically linked Rust decompression and must remain counted as a dependency. CPU medians for a fresh helper plus Git are Rust/C 10.024/10.083 ms for clean, 5.270/5.315 ms for dirty and 5.561/5.642 ms for untracked repositories. These results support proceeding with a full C runtime prototype, where the bridge can disappear; they do not justify enabling this mixed implementation by default.

## Measurement and reproduction

The source baseline is `282331ad0c262e4414e6c5d9e783a9b065f63ca3` plus the exact retained prototype inputs. The corrected Rust counterfactual first removes the inherited-pipe reader join; its independent acceptance is recorded in [the pipe-lifetime report](../git-pipe-lifetime-2026-09-08/report.md). This comparison builds both feature selections from the same tree with the same release toolchain. The comparison installer copies the same accepted native payload, replaces only the runtime, refreshes its development manifest and dynamic dependency list, and verifies both installations through the real manager. All artifacts are unsigned development installations.

Collection has 50 alternating pairs for each of three 1,000-file states and two helper-lifetime modes, totaling 600 samples. Each pair compares complete snapshots. Fresh-helper collection begins after the ready handshake; it does not claim an evicted filesystem cache. Compare implementations within each state, since the clean state follows fixture creation while the other states follow reset and mutation. Native readiness has 50 alternating pairs per prompt and observes the primary OSC 133 editable marker. Those measurements and the retained memory and trace gates use CPU 0, with timing workloads run sequentially. Initial unpinned memory/trace runs remain diagnostic evidence; the CPU-0 runs determine the gates. Retained memory uses the existing plain Zsh 5.9.2 versus Zsh-plus-integration workload, rather than total native-distribution memory.

`metadata.json` records source and binary hashes, compiler identities, flags, exact commands and linked libraries. `inputs.tar.gz` retains implementation and harness bytes; `results.tar.gz` retains passing and failed checks, fixtures, manifests and raw timing rows. `verify-native-git-evidence.py` checks identities, counts, failure/correction evidence and resource-gate arithmetic through the shared retained-evidence entrypoint.
