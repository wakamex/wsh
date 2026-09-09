# Native lazy history filtering cuts a 10,000-duplicate scan from 229.68 to 62.54 ms

The C prototype preserves lazy result filtering and reduces median time by 72.77% when skipping 10,000 real history records containing the same command. Four configuration modes pass 440 exact state transitions against the pinned plugin in both release and sanitized builds. The test includes multiline and shell-metacharacter commands, exhaustion, an existing empty filter value, and new history between calls.

| Duplicate history records | Reference median | C median | Reduction | Paired p95 change |
|---|---:|---:|---:|---:|
| 100 | 1.146 ms | 0.056 ms | 95.09% | -1.079 ms |
| 10,000 | 229.682 ms | 62.543 ms | 72.77% | -161.599 ms |

## Retain the partial port for a decision

The measured gates pass. The prototype replaces only `_history_substring_search_process_raw_matches`; the initial search already uses native Zsh matching. Navigation, cursor/buffer state, highlighting, keymaps and plugin ownership remain with the existing implementation. The module uses the same live history parameter and associative-array implementation and preserves the raw-index and result-array state after each call. A complete native editor-component replacement has not been established, and no production integration loads the prototype.

The measured advantage applies when uniqueness is enabled and a long run of duplicates must be skipped. It does not establish a general keystroke speedup: uniqueness is disabled by default, and the ordinary path usually consumes one result. Adopting an additional native interface for this case remains a decision. Full real-ZLE and OMZ qualification of the partial port is still required before adoption; the existing implementation and its tests remain selected.

## Failures and measurement correction

The initial C version dereferenced an unallocated empty associative-array table. UndefinedBehaviorSanitizer identified the exact access. The corrected version creates the table through the same native parameter API used by Zsh and passes the final sanitizer matrix. The initial failing source and outputs are retained.

An initial timing fixture repeated one history index. The final fixture uses distinct real history indices whose command text is identical. Both are retained, but only `timing-final` supports the table and gates. The larger native time in the real fixture reflects actual history lookup work and is not discarded.

## Method and implementation scope

Start from `546b221` and the unsigned native installation identified in metadata. Each count has 50 alternating pairs pinned to CPU 0. History population, result reset and the first accepted match occur outside timing. The measured call skips the remaining duplicates and reaches exhaustion; both variants must return status 1 with the final raw index equal to the fixture size. Timings use `EPOCHREALTIME`; the paired p95 is the 48th sorted difference of 50. The fixed gates are at least 20% median reduction at 10,000 records and no more than +1 ms paired p95 regression.

The sanitizer module uses AddressSanitizer and UndefinedBehaviorSanitizer with the previously instrumented native host. The documented upstream host exceptions disable leak detection and function sanitization. Final runs produce no diagnostics. No user history, configuration or production source was modified. The C module, test harness, configured headers, exact commands, binaries' hashes, initial failure and all raw results are retained. The full plugin and its adapters remain maintained; no dependency is counted as deleted.
