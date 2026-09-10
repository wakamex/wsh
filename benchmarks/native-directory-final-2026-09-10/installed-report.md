# Native directory ownership passes installed qualification

Native development installations now select the C directory owner when Wsh owns directory jumping. Complete command measurements improve median lookup by 54.2% at 100 records and 83.7% at 1,000 records; writes improve by 54.7% and 83.9%. Installed startup passes the fixed +3 ms paired p95 gate with both existing and minimal prompts. The comparisons use 50 alternating pairs, after installed correctness and sanitizer tests.

| Workload | Pinned Zsh owner median | Native owner median | Paired p95 change |
| --- | ---: | ---: | ---: |
| Complete command lookup, 100 records | 11.329 ms | 5.185 ms | -4.854 ms |
| Complete command write, 100 records | 11.705 ms | 5.304 ms | -5.017 ms |
| Complete command lookup, 1,000 records | 52.542 ms | 8.540 ms | -42.951 ms |
| Complete command write, 1,000 records | 52.233 ms | 8.387 ms | -42.471 ms |
| Installed startup, existing prompt | 23.511 ms | 23.205 ms | +1.880 ms |
| Installed startup, minimal prompt | 25.686 ms | 25.235 ms | +2.039 ms |

## Integration and correctness

The shared C implementation is compiled into the native shell; the optional module driver includes the same source for experiments. The generated adapter retains pinned Zsh configuration, hooks, completion widgets, help, and unload behavior while replacing the data/query function. Both the adapter and the original plugin are precompiled. The original source remains available for compatibility and legacy installations. Existing external commands or plugins retain ownership.

The integrated implementation passes 720 query comparisons, ten mutation cases, actual flock contention and twenty mixed writers, removal/re-entry/reload lifecycle, custom cd and unload, whole-database confirmation, and three actual ZLE completion cases in normal and address/undefined sanitizer runs. The tab-containing-path case intentionally preserves literal bytes where the pinned owner corrupts the path. The integrated sanitizer binary also passes real writable and read-only file mounts. The final precompiled payload passes all nine installed component contracts, including actual Oh My Zsh coexistence. The same C binary with the uncompiled adapter passed 18 startup/state/context/relocation cases and five recovery cases. The fresh host build passed upstream Zsh's suite.

## Measurements and retained failures

Command tests start a fresh shell and source either the pinned function or native adapter before each lookup/write, using the same installed binary and instrumentation. Startup tests compare the previous selected history/completion installation with the complete native directory installation, observing primary OSC 133 readiness on CPU 0 with tracing disabled. Builds and correctness tests completed before timing.

The first adapter was not precompiled and failed minimal-prompt startup at +3.844 ms paired p95. Applying the existing plugin precompilation treatment passes the unchanged gate; both runs are retained. An earlier assembly attempt created the adapter directory before copying the vendor tree and produced an extra nested directory; moving adapter installation after that copy fixes the layout. Neither failure required a C behavior change.

Final unsigned installation: e0da4c91baf8a35e35e7dc77617da45703cdd16ff0a3e62747913c7282f59e13. Exact input hashes, binary and manifest identities, commands, fixtures, raw samples, logs, and summaries are retained in installed-identity.json and installed.tar.gz. glibc 2.28 qualification follows separately. This does not update installed users or publish a release.
