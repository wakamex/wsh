# Disabling the executable OMZ theme removes one redundant Git execution

Changing only `ZSH_THEME="wakamex"` to `ZSH_THEME=""` in a private copy of the actual configuration removed Wakamex's collector hooks while preserving Wsh's displayed Git prompt and the tested editing behavior. Git executions per no-op transition fell from five to four. Median prompt-return latency fell from 59.285 ms to 56.464 ms; startup p90 fell from 953.398 ms to 949.255 ms.

Both configurations passed interactive checks before a 40-pair comparison using the same Wsh bundle, startup dependencies, Git fixture and native readiness boundary. Process tracing ran separately. The result establishes a small prompt-transition and process-count benefit; the larger startup costs remain in the other configuration code.

## Normal Wsh comparison

| Measurement | Actual configuration with executable Wakamex theme | Same configuration with OMZ theme disabled |
|---|---:|---:|
| Startup median | 934.444 ms | 923.139 ms |
| Startup p90 | 953.398 ms | 949.255 ms |
| No-op prompt-return median | 59.285 ms | 56.464 ms |
| No-op prompt-return p90 | 61.162 ms | 58.152 ms |
| Git executions per no-op transition | 5 | 4 |
| Python helper executions per no-op transition | 1 | 1 |
| Wakamex Git request hook | Present | Absent |
| Wakamex preexec hook | Present | Absent |
| Wakamex shutdown hook | Present | Absent |
| Displayed prompt owner | Wsh | Wsh |

Within paired observations, theme-off minus normal startup time had median -8.005 ms and p90 +5.087 ms. Prompt-return differences had median -2.542 ms and p90 -1.271 ms. Startup variability can exceed the small theme-related saving. All measured observations remain in the result; the acceptance gate required preserved behavior and at least one fewer Git execution, rather than a large startup improvement.

## Preserved behavior and remaining work

Both variants passed startup, command execution, alias/completion-state checks, filename TAB completion, Ctrl-C and prompt return. Direct ZLE probes confirmed substring history recall, the expected autosuggestion suffix, and visible syntax-highlight regions. Wsh retained one runtime `precmd`, `preexec` and shutdown hook. The actual autosuggestions and syntax-highlighting versions remained externally owned. The Wsh prompt still displayed the fixture's `main` branch and matched `WSH_LAST_PROMPT` after asynchronous collection.

The disabled-theme case had no Wakamex Git request function or registered request, preexec or shutdown hook. Configured `git-fetch-all` and `update_current_git_vars` functions remained present. The retained Python helper and other Git work belong to remaining configured functionality and require their own diagnosis. Theme removal does not authorize unloading those plugins.

The startup process trace caught a timed git-auto-fetch invocation in the baseline only, including a `date` execution. Its larger startup Git-count difference is not attributed entirely to the theme change. The no-op comparison began after startup work settled and recorded the expected single-execution reduction, five versus four.

## Fixture and measurement

The [shared plan](../profile-readiness-plan-2026-09-05.md) fixed this as a private configuration counterfactual after correcting profiling readiness. The Wsh presentation remains minimal in both cases. OMZ itself, the seven configured plugins, NVM/SDKMAN and other initialization remain enabled. [The sole source change](startup-change.diff) replaces one theme assignment. Startup files and identified dependencies were checked against the prior private snapshot before running; live startup-file hashes remained unchanged afterward.

The final comparison uses unsigned development bundle `3c9a72bc38696e85ed95ccb61f5f502eaa949b490aaed5796175ef87ecc8fa04`. [Metadata](metadata.json) records binary and private-input hashes, the fixture tree and exact command; the [preceding readiness result](../profile-readiness-2026-09-05/metadata.json) supplies the complete target, build, Zsh, toolchain and host identity. Both cases load the same selected bundle's module/function paths. The fixture contains 1,000 numbered tracked files plus one completion filename, branch `main`, and no remotes.

Timing uses five warmups per variant followed by 20 forward and 20 reverse interleaved pairs, nearest-rank p90, and CPU 0 affinity on a shared host. It measures interactive non-login startup through the common ZLE observer and native OSC 133 `B`, then one no-op command after a 150 ms settling interval. No Wsh profiling or strace runs during those timing samples. Process traces use a separate 400 ms settling interval and retain only successful executable events in the public export.

The first run reused the prior matrix's old bundle path in its common startup adapter. It passed behavior/process checks but could include duplicate completion-search directories. That complete run remains in [stale-bundle-path-control](stale-bundle-path-control/summary.tsv), and its private inputs remain at `/var/tmp/wsh-omz-theme-off-stale-path-control-2026-09-05`. The final run rebinds the common adapter paths to the selected bundle on both sides. This fixture correction was recorded before the final run and did not change the theme-only difference between cases.

## Evidence and reproduction

[Raw samples](samples.tsv), [summary](summary.tsv), [correctness](correctness.tsv), [process events](process-events.tsv), [process counts](process-counts.tsv), and [trace interval boundaries](process-intervals.json) retain the final comparison. Public process events omit arguments. Private startup files, caches and terminal/process transcripts remain under `/var/tmp/wsh-omz-theme-off-2026-09-05`; the original startup/dependency snapshot remains under `/var/tmp/wsh-real-config-2026-09-05`. Reproduction of this actual-configuration experiment requires those private inputs. `SHA256SUMS` binds the public evidence and tools.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/benchmark-omz-theme-off.py <new-output-directory> <new-private-work-directory> /var/tmp/wsh-real-config-2026-09-05 <bundle>
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/verify-omz-theme-off-evidence.py
```

The experiment changed private test copies. Adopting the one-line change in live configuration remains a separate action. This result supports explicit selection of Wsh's presentation with the executable OMZ theme disabled; it does not implement legacy-renderer selection or generic theme-hook removal.
