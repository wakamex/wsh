# Oh My Zsh z plugin versions since October 2022

Wsh 0.4.5 recognizes all ten versions of the `z` plugin that Oh My Zsh has bundled since October 2022 and hands their directory jumping to the native implementation. Before, it recognized two. Recognition now looks up references by component and file size, so the larger catalog costs nothing measurable at startup. With all five recognized plugins loaded, 0.4.5 starts up no slower than 0.4.4 within the 3 ms gate.

## Catalog entries

The eight new entries are the `plugins/z/z.plugin.zsh` files at Oh My Zsh commits `7e3231b`, `2e7a247`, `667fdbf`, `048e166`, `3f8ea81`, `d50115a`, `2d58417` and `c24960c`, which together with `9112b53` and `d745fbf` cover every change to the file since October 2022. Each snapshot is retained unchanged under `third_party/plugin-catalog/snapshots/` with its embedded license notice. Versions before August 2026 do not define `_zshz_realpath` or `_zshz_zle_completion_widget`, so the directory handoff checks those helpers only when they exist.

## Results

| Check | Result |
| --- | --- |
| Catalog checks | 27 snapshots and fingerprints verified; input bounds and upstream mapping checks pass |
| Live upstream check | All six configured mappings are known |
| Handoff matrix | 107 cases pass through the catalog and 107 through the local Git check, including exact handoff, modified-copy rejection and function-override preservation for each of the ten `z` versions |
| Installed suite | The complete installed suite passes on the 0.4.5 native installation `7cf9725d` |

| Startup workload, all five recognized plugins | 0.4.4 median readiness | 0.4.5 median readiness | Paired p95 added readiness | Gate |
| --- | ---: | ---: | ---: | --- |
| Existing prompt | 57.33 ms | 55.83 ms | 0.32 ms | <= 3 ms, pass |
| Wsh minimal prompt | 34.24 ms | 32.85 ms | 2.00 ms | <= 3 ms, pass |

Each workload uses 50 alternating pairs against the 0.4.4 installation `c667f897`.

The recognition microbenchmark times the catalog lookup alone, with the Git check disabled, on the 0.4.4 installation before and after replacing its lookup and table with the size-indexed ones:

| Lookup, median of two runs each | 0.4.4 | Size-indexed |
| --- | ---: | ---: |
| Edited `z` copy, not recognized | 252 to 282 us | 66 to 69 us |
| Recognized zsh-autosuggestions | 1.08 to 1.17 ms | 0.48 to 0.54 ms |
| Recognized `z` | 1.07 to 1.27 ms | 0.99 to 1.00 ms |

[Identity](identity.json) records the installations and sources; [evidence](evidence.tar.gz) retains the raw samples, summaries, matrix results, upstream check, suite log and the microbenchmark with its inputs, covered by `SHA256SUMS`.
