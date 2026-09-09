# Native history selection reduces suggestion lookup at 10,000 entries

The C strategy reduces median recent-match lookup from 0.747 to 0.021 ms and absent-prefix lookup from 1.207 to 0.400 ms at 10,000 real history entries. The smaller builtin-quoting change preserves results but provides no median improvement in these workloads. All three strategies agree on 6,054 suggestions in release and sanitized tests, including literal pattern characters, Unicode, multiline prefixes, ignore patterns and new history between queries.

| History entries and query | Reference median | Builtin quote median | C median | C reduction from builtin |
|---|---:|---:|---:|---:|
| 100, recent matching command | 0.0327 ms | 0.0329 ms | 0.0188 ms | 42.75% |
| 100, absent prefix | 0.0377 ms | 0.0377 ms | 0.0226 ms | 39.87% |
| 10,000, recent matching command | 0.7467 ms | 0.7492 ms | 0.0210 ms | 97.20% |
| 10,000, absent prefix | 1.2071 ms | 1.2138 ms | 0.3997 ms | 67.07% |

## Retain the strategy prototype for a decision

The focused C strategy passes its fixed parity and timing gates. It traverses the native history ring directly, while the reference uses the history parameter's scanning interface. The builtin-only counterfactual replaces the reference's prefix-escaping substitution with `${(b)1}`, as suggested by its upstream comment. Neither variant replaces autosuggestion cancellation, asynchronous work, acceptance, custom widget wrapping or stale-result handling. The complete plugin and ownership adapter remain selected, and no production path loads the private module.

The C strategy is worth retaining for a future integrated comparison, but these measurements alone do not establish the complete editor component's latency or simplification. Adoption needs full real-ZLE, custom-widget and OMZ qualification and a decision about maintaining a partial native interface. No plugin dependency has been deleted. The builtin-only change remains a counterfactual because it did not improve the measured workload.

## Compatibility finding

The initial C version returned an empty suggestion for malformed ignore patterns. Actual Zsh history parameter matching leaves the scan unfiltered when pattern compilation fails, so the reference returns the newest history value in that case. The corrected C strategy preserves that behavior. The initial failed comparison and source are retained. This experiment does not change that user-visible contract.

## Method and scope

The source baseline is `4cf9d07` and the unsigned native installation is identified in metadata. Each of four workloads has 50 matched rounds across the reference, builtin-only and C variants on CPU 0. Alternate rounds reverse the order. History population, function setup and warmup occur outside timing. Every measured output is checked against the expected recent command or empty result. Timings use `EPOCHREALTIME`; paired p95 changes use the 48th sorted difference of 50. Both candidates pass the +1 ms paired p95 regression gate, and C exceeds the required 20% median reduction beyond the builtin counterfactual at 10,000 entries.

The sanitizer module uses the existing instrumented native Zsh host with its documented leak/function-sanitizer exceptions. The final matrix produces no diagnostics. The initial comparison had 4,036 cases; the final 6,054-case matrix adds malformed patterns and history mutation between groups. Exact generated fixtures, source and binary identities, commands, raw output and timing samples are retained. These are history-strategy measurements with async and editor machinery held outside the changed boundary.
