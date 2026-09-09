# Highlighting cost is concentrated in the parser loop

The main parser loop accounts for about 40% of long redraw time. Style fallback accounts for about 13%, and command classification reaches about 6% in the distinct-command workload. Profiling 50 paired redraws per workload therefore does not justify another small helper port under the fixed 20% whole-redraw improvement gate. Keep the existing highlighter; a substantial parser port is a separate decision.

| Complete redraw workload | Unprofiled median | Profiled median | Paired p95 profiling overhead |
| --- | ---: | ---: | ---: |
| Short `echo hello` | 0.829 ms | 0.842 ms | 0.063 ms |
| 100 repeated commands | 79.205 ms | 80.241 ms | 2.322 ms |
| 100 distinct commands | 84.235 ms | 85.280 ms | 1.844 ms |
| Multiline conditional with parameter expansion | 3.680 ms | 3.711 ms | 0.077 ms |

| Operation in the distinct-command workload | Median calls per redraw | Median exclusive time | Approximate share of profiled redraw |
| --- | ---: | ---: | ---: |
| Main token/parser loop | 1 | 34.225 ms | 40.1% |
| Style fallback construction | 300 | 11.220 ms | 13.2% |
| Paint orchestration | 1 | 5.860 ms | 6.9% |
| Command type helper, including its surrounding logic | 200 | 5.240 ms | 6.1% |
| Argument highlighting, excluding callees | 100 | 5.090 ms | 6.0% |

Zsh's own function profiler supplies call counts and exclusive/inclusive times. Each paired call uses the same buffer with the command cache cleared; profiler loading, report writing and unloading happen outside the measured redraw. All 200 pairs produce identical nonempty highlight regions. The roughly 1 ms median profiling cost on long buffers is measured separately and is not counted as an optimization. Exclusive function times identify an area for further investigation, not individual statements within the parser loop.

Even eliminating style fallback entirely would recover only about 13% of the distinct-command redraw in this workload. That counterfactual rules out treating a fallback-only C port as sufficient for the 20% gate. The earlier classifier port already failed its whole-redraw gate. A complete or substantial parser port could address more cost, but would need the upstream syntax corpus, multiline/alias/expansion/style semantics, actual editor composition, sanitizers and new complete-redraw measurements. No parser candidate or selected implementation change was made in this slice, so no new upstream-suite or sanitizer result is claimed for one.
