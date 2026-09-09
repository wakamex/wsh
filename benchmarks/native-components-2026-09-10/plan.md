# Complete component ownership and bounded initialization experiments

Start from the clean native qualification at `6d8d9ff`, using the unsigned host installation `4bfc1bd9af7cf33c315f62a65db66eceb64a9ffba4585144b7ee2732106f0986` and its C helper. Work sequentially through directory jumping, history substring search, autosuggestions, completion registration scanning and highlighting attribution. Commit each causal component independently with its tests, measurements and decision. No publication, push, live dotfile changes or account-shell changes.

## Directory jumping

The existing partial query port cuts the 1,000-entry workload from 45.146 to 17.043 ms but retains the complete plugin and an internal parameter interface. Prototype a C owner for database reading, ranking/query, add/remove, locking and persistence, with thin Zsh registration, custom-cd and completion/editor adapters where native Zsh APIs remain the simpler interface. Preserve the documented ZSHZ configuration and existing database on the supported Linux target. Compare against the actual pinned plugin, including CLI status/output, unusual path bytes, case/trailing/uncommon matching, ranking/aging, exclusions, symlinks, lock contention/concurrent writers, completion, custom commands and unload/reload. Run normal and sanitizer correctness before 50 alternating pairs at 100/1,000 entries for query and write; require at least 20% median lookup improvement at 1,000 entries, at most +3 ms paired p95 on writes/startup, and no weakened persistence or ownership semantics. Unsupported behavior or extra compatibility machinery requires an explicit retained decision instead of default adoption.

## History substring search

Move beyond the duplicate-filter kernel to a complete native navigation state machine while preserving bindings, live-history updates, uniqueness/fuzzy/prefix options, buffer/cursor state, multiline history, reset, custom widgets and highlight composition. Compare real ZLE transcripts against the pinned plugin, normal and sanitized, then 50 alternating pairs for ordinary default navigation and duplicate-heavy uniqueness mode. Require no more than +1 ms paired p95 editing regression and at least 20% median reduction in the declared large-history workload; count retained glue and actually removable plugin source.

## Autosuggestions

Prototype complete feature ownership including selection, asynchronous cancellation/results, stale-result rejection, acceptance, widget wrapping, configuration and history changes. The builtin quoting counterfactual previously showed no gain. Compare the real plugin in actual ZLE, custom/vi widgets, rapid edits, history/completion strategies and disable/re-enable behavior; sanitize before 50 paired small/large-history editing and acceptance runs. Require no more than +1 ms paired p95 editing regression, at least 20% median improvement in the declared large-history selection workload, bounded resources and no new process per ordinary edit. Retain a prototype if simplifying ownership would require breaking supported configuration.

## Completion registration scanning

Keep compaudit, invalidation, registration semantics, user function priority and dump ownership unchanged. Replace only the demonstrated per-file header registration scan with a native scanner and compare against actual compinit. Test missing, reusable, stale and unusable dumps, hostile/duplicate/custom headers, security refusal, representative Git/path/directory completions and first/second Tab. After correctness, use 50 alternating pairs per cache state with existing +20 ms warm / +100 ms cold-fallback startup budgets and 100 ms first-Tab p95. No broker, daemon, audit bypass or new completion language.

## Syntax highlighting attribution

The previous classifier-only port failed its 20% gain gate. First profile complete redraws on short, multiline and repeated/distinct 100-command workloads, separating parser/classifier/path/highlight construction cost. Verify instrumentation overhead separately. Prototype only a dominant operation or a small complete path supported by the attribution. Require exact upstream and real-ZLE region parity, sanitizers, and 50 paired complete redraws with at least 20% median improvement on the declared target and at most +1 ms paired p95 regression elsewhere. Otherwise retain the finding and existing highlighter.

## Bounds and final checks

At each gate, stop after two failed interventions or two hours and audit the hypothesis before another intervention. A new hypothesis must name its evidence and remaining scope; do not extend scope into a framework to rescue a failed port. Preserve failures, effective configuration, source/binary hashes, fixtures, raw timings and summaries. No builds or verification overlap CPU-0 timings. Accept only measured, compatible simplifications; keep decision-dependent prototypes disabled. Run applicable integrated native contracts and the complete retained-evidence verifier, and leave atomic local commits with an explicit result for all five components.
