# Real configurations retain editing behavior, with theme overlap and profiling-gate failures

Wsh passed the tested startup and editing behavior with plain configuration, Oh My Zsh, representative themes, recognized plugin copies, and the user's actual setup. The actual configuration reached editor readiness at 1,056.849 ms p90 under Wsh versus 1,005.672 ms under the same bundled Zsh. Executable theme appearance is replaced, some theme collectors remain active, and the stricter editor-readiness profiling gate failed.

The experiment checked 27 configuration/launch combinations, collected 40 warm timing observations for each, exercised actual ZLE editing, and recorded separate process and function traces. The product implementation and user startup files were unchanged. This is a completed compatibility and profiling experiment with specific follow-ups, not a clean release-readiness result.

## Startup latency

| Configuration | Bundled Zsh median | Bundled Zsh p90 | Wsh median | Wsh p90 | Wsh minus bundled Zsh p90 |
|---|---:|---:|---:|---:|---:|
| Empty user configuration | 5.026 ms | 5.370 ms | 28.463 ms | 28.975 ms | +23.605 ms |
| Plain .zshrc with alias and option | 5.122 ms | 5.433 ms | 28.510 ms | 29.035 ms | +23.603 ms |
| Oh My Zsh without theme or plugins | 43.977 ms | 44.708 ms | 70.361 ms | 71.668 ms | +26.960 ms |
| Oh My Zsh with robbyrussell | 48.952 ms | 50.439 ms | 87.287 ms | 88.470 ms | +38.030 ms |
| Oh My Zsh with agnoster | 89.157 ms | 89.917 ms | 71.496 ms | 73.135 ms | -16.782 ms |
| Oh My Zsh with Wakamex | 50.977 ms | 52.038 ms | 77.724 ms | 79.829 ms | +27.791 ms |
| Oh My Zsh with three recognized editing plugins | 69.159 ms | 70.504 ms | 80.889 ms | 82.774 ms | +12.270 ms |
| Oh My Zsh with Wakamex and three recognized editing plugins | 76.432 ms | 78.172 ms | 88.323 ms | 89.898 ms | +11.726 ms |
| User’s actual startup configuration | 978.799 ms | 1005.672 ms | 1037.114 ms | 1056.849 ms | +51.177 ms |

Wsh's empty-configuration increment is 23.605 ms at p90. It includes the three editing defaults and managed runtime that the empty direct-Zsh control does not supply. After subtracting that increment, robbyrussell adds a further 14.426 ms, exceeding its predeclared 5.044 ms investigation threshold. No other configuration crosses that startup trigger. The actual setup adds 27.572 ms beyond the empty increment, below its 100.567 ms threshold; its approximately one-second total startup still warrants configuration-level investigation.

Agnoster's lower Wsh latency accompanies replacement of its original prompt. That row cannot establish a same-presentation speedup. Likewise, loading a legacy theme under Wsh does not mean its appearance was preserved.

## Actual configuration startup costs

Across the default-profile samples, median `.zshenv` time was 700.273 ms and `.zshrc` time was 272.607 ms. Wsh's history adapter took 3.141 ms, autosuggestion ownership check 0.364 ms, syntax ownership check 0.399 ms, and integration span 2.500 ms. The initial Git child took 11.267 ms median and ran asynchronously after editor readiness.

The separate warm-cache function profile recorded these largest self times: `nvm_auto` 306.230 ms, `compinit` 163.010 ms, `nvm` 114.600 ms, `compdef` 112.040 ms, `compdump` 90.840 ms, and `nvm_ensure_version_installed` 57.700 ms. `update_current_git_vars` took 35.740 ms. Function instrumentation is a different workload, so these values identify candidates rather than predicting uninstrumented savings.

The process trace recorded 119 external `printf` executions, two `brew` executions, one `fnm`, and one `node` during actual-config startup. Total successful exec events were 234 for direct Zsh and 237 for Wsh; the latter adds launcher execution, runtime execution, and its Git scan. Exec events count successful program replacements, including multiple replacements in the same PID, rather than distinct simultaneously resident processes. Full arguments remain private.

There is a median 59.133 ms gap between Wsh integration completion and its first runtime `precmd` span in this configuration. The report's `First precmd` field measures Wsh's hook, not the complete chain of user and theme hooks. The retained function trace identifies Git-variable work in that chain. Default span labels should make this boundary explicit before treating the profile as complete hook attribution.

## Prompt ownership and Git work

| Configuration | Direct Zsh Git executions per no-op transition | Wsh Git executions per no-op transition | Observed ownership or retained work |
|---|---:|---:|---|
| Empty user configuration | 0 | 1 | Wsh owns the displayed prompt and its one Git scan |
| Plain .zshrc | 0 | 1 | User alias and option coexist with the Wsh prompt |
| Oh My Zsh without theme or plugins | 0 | 1 | OMZ loads; Wsh supplies the Git prompt |
| Oh My Zsh with robbyrussell | 5 | 6 | OMZ async Git collection remains while Wsh displays its own prompt |
| Oh My Zsh with agnoster | 16 | 1 | Replacing the prompt eliminates evaluation of agnoster's synchronous Git expressions |
| Oh My Zsh with Wakamex | 1 | 2 | Wakamex Git worker and lifecycle hooks remain alongside Wsh |
| Oh My Zsh with three recognized editing plugins | 0 | 1 | Recognized editing implementations have one effective owner |
| Oh My Zsh with Wakamex and three recognized editing plugins | 1 | 2 | Editing ownership passes; Wakamex's collector remains |
| User's actual startup configuration | 4 | 5 | Wakamex, git-prompt and git-auto-fetch hooks remain; both variants also execute one Python helper |

The additional robbyrussell and Wakamex collectors cross the predeclared duplicate-work gate. The actual configuration also intentionally enables git-auto-fetch; its repository check should not be removed merely because it executes Git. Diagnosis must distinguish that configured behavior from collectors whose output no longer owns the displayed prompt.

History substring search uses Wsh ownership in every managed case. Pinned autosuggestions uses Wsh ownership. Pinned syntax highlighting uses its supported `external-exact` activation path, which preserves one effective implementation. The user's older autosuggestions and syntax-highlighting copies remain `external-unknown`, and the direct ZLE probes confirm that both still work.

## Profiling overhead and observer control

| Configuration | Paired profile overhead median | Paired profile overhead p90 | 3 ms p90 gate |
|---|---:|---:|---|
| Empty user configuration | 2.498 ms | 3.079 ms | Fail |
| Plain .zshrc with alias and option | 2.519 ms | 3.257 ms | Fail |
| Oh My Zsh without theme or plugins | 2.815 ms | 3.428 ms | Fail |
| Oh My Zsh with robbyrussell | 3.165 ms | 4.141 ms | Fail |
| Oh My Zsh with agnoster | 2.577 ms | 3.532 ms | Fail |
| Oh My Zsh with Wakamex | 2.573 ms | 3.995 ms | Fail |
| Oh My Zsh with three recognized editing plugins | 3.139 ms | 4.585 ms | Fail |
| Oh My Zsh with Wakamex and three recognized editing plugins | 2.847 ms | 4.574 ms | Fail |
| User’s actual startup configuration | 10.014 ms | 33.472 ms | Fail |

The matrix's readiness observer runs after startup-installed ZLE line-init hooks and then waits for native OSC 133 `B`. The existing profile acceptance benchmark stops when it sees the visible `% ` prompt. Repeating that unchanged benchmark with this same bundle produced 2.710 ms paired p90 overhead across 100 pairs, passing its existing gate. The stricter matrix observation produced 3.079 ms on empty configuration. These controls also use different PTY harnesses and differ by the completion fixture file and common observer hooks, so they do not isolate observation position as the sole cause of the numerical difference. The older passing result does not establish an end-of-editor-initialization pass.

An additional 20-pair A/A control launched the identical unprofiled shell in alternating orders. Its B-minus-A p90 was 0.667 ms for empty configuration and 11.720 ms for actual configuration; maximum absolute actual-config difference was 70.252 ms. Startup variability therefore contributes materially to actual-config paired differences. The measured 33.472 ms profile p90 remains a failed gate, but it does not establish that trace recording alone costs 33.472 ms. No samples from the completed timing matrix were excluded, and no threshold was relaxed.

## Correctness and validation

All 27 matrix combinations passed initial readiness, a synthetic alias, filename TAB completion, Ctrl-C recovery, and command/prompt return. Plain-configuration aliases and the actual configuration's existing alias/completion and NVM/SDKMAN function state were present. All managed combinations had exactly one Wsh `precmd`, `preexec`, and shutdown hook. Twelve direct ZLE checks passed substring history recall, the expected autosuggestion suffix, and nonempty syntax-highlight regions: every managed configuration plus direct Zsh with recognized plugins, Wakamex plus plugins, and the actual setup.

Before timing, the bundle passed the existing startup-order/RCS tests, profile privacy and recovery tests, history-search tests, autosuggestion tests, syntax-highlighting tests, plugin-doctor tests, foreground argv/job-control tests, and native OSC producer PTY tests. The initial foreground test invocation omitted its required mode; the corrected `candidate` invocation passed and both invocations remain in the log. The canonical glibc 2.28 suite, full Rust suite, live CI and release workflows were not rerun for this experiment. The measured artifact is an unsigned host development bundle.

## Workload and evidence

The bundle and manager were built from clean source `3decf521a13d98b9e0f50c64c666766406800205`, before adding experiment files. Bundle digest is `f2a1bf90a1ff0312c2ad6c2389e2f19b8fd1a9de1e706c14ec0b0e34ca667581`; Zsh source is `cad0d67c76e2be7371cf3526b79ea2581810d35a`. Exact build, binary, source, patch, target, toolchain and host identities are in [metadata.json](metadata.json), [inputs.json](inputs.json), and the compressed canonical [bundle manifest](bundle-manifest.json.gz).

Both variants use the exact bundled Zsh and its module/function paths, disable the unanswered native terminal query, and load the same configuration content. Every child is pinned to CPU 0; the CPU was not reserved and other host services remained active. Each configuration has isolated completion caches per variant, five warmups, then 20 forward and 20 reverse interleaved direct/normal/profile triples. The PTY fixture has 1,000 numbered tracked files plus one tracked completion filename, branch `main`, and no remotes. Statistics use nearest-rank p90. These are warm completion-cache measurements; filesystem caches were not forcibly cleared. The table represents interactive non-login startup. Existing dedicated tests cover login startup order, but actual-login latency was not measured.

Actual startup files were copied privately while retaining the real HOME and installed dependencies. History writes and completion caches were redirected into experiment storage. The startup-file hashes and aggregate dependency hash are public; the 575 identified dependency files, private snapshots, full process arguments and terminal transcripts are retained under `/var/tmp/wsh-real-config-2026-09-05` with a private parent directory. Reproducing the actual-configuration row requires those private inputs. Synthetic inputs use the exact Git revisions in `inputs.json`. The observer corrections and bounded follow-up controls are documented in the [predeclared plan](../real-config-plan-2026-09-05.md).

[Raw timings](timing.tsv), [summaries](summary.tsv), [gates](gates.tsv), [component spans](spans.tsv), [span summaries](span-summary.tsv), [default trace archive](profile-traces.tar.gz), [process events](process-events.tsv), [process counts](process-counts.tsv), [editing results](editing.tsv), [A/A controls](control.tsv), [control summary](control-summary.tsv), and [existing-observer control](percent-prompt-summary.tsv) retain the accepted run. TSV serialization uses LF line endings and `-` for absent detail fields; the original TSV bytes are also retained privately. Public process events contain executable basenames without arguments. Function reports are separate diagnostic workloads, including [the actual setup](actual-functions.txt). `SHA256SUMS` binds the evidence and experiment tools.

## Follow-up experiments

1. Correct the profiling acceptance observer and clarify Wsh-only hook-span labels. Preserve the stricter failed results before considering any profiling optimization.
2. Profile configuration-owned eager NVM initialization and repeated completion setup with one reversible, private configuration counterfactual at a time. The existing lazy SDKMAN wrapper is followed by eager SDKMAN initialization in the startup files; that is a concrete configuration candidate rather than a reason to rewrite arbitrary hooks in Wsh.
3. Address legacy presentation choice explicitly. The smallest counterfactual is selecting a Wsh presentation with the executable OMZ theme disabled in a test copy, or preserving the legacy renderer while omitting Wsh's renderer. Generic hook unloading remains unjustified. Installed-user theme selection and legacy-renderer mode are not implemented by this experiment.

## Reproduction

```sh
./build/build-development-bundle.zsh
python3 benchmarks/benchmark-real-config.py prepare benchmarks/NEW-RUN /var/tmp/NEW-PRIVATE-RUN bundles/BUNDLE
python3 benchmarks/benchmark-real-config.py correctness benchmarks/NEW-RUN /var/tmp/NEW-PRIVATE-RUN bundles/BUNDLE
python3 benchmarks/check-real-config-editing.py benchmarks/NEW-RUN /var/tmp/NEW-PRIVATE-RUN bundles/BUNDLE
python3 benchmarks/benchmark-real-config.py timing benchmarks/NEW-RUN /var/tmp/NEW-PRIVATE-RUN bundles/BUNDLE
python3 benchmarks/summarize-real-config.py benchmarks/NEW-RUN
# Diagnostics warm each functions variant once before observation.
python3 benchmarks/benchmark-real-config.py diagnostics benchmarks/NEW-RUN /var/tmp/NEW-PRIVATE-RUN bundles/BUNDLE
python3 benchmarks/benchmark-real-config.py control benchmarks/NEW-RUN /var/tmp/NEW-PRIVATE-RUN bundles/BUNDLE --configs empty actual
python3 benchmarks/export-real-config-evidence.py /var/tmp/NEW-PRIVATE-RUN benchmarks/NEW-RUN
python3 benchmarks/verify-real-config-evidence.py
```

The preparation tool archives the source locations and exact pins declared at its top; the OMZ pin was fetched into private experiment storage because the existing checkout lacked that commit. The original percent-prompt control used `./benchmarks/benchmark-profile.zsh benchmarks/real-config-2026-09-05/percent-prompt-control.tsv target/release/wsh bundles/f2a1bf90a1ff0312c2ad6c2389e2f19b8fd1a9de1e706c14ec0b0e34ca667581 50`, followed by `./benchmarks/summarize-profile.zsh` with `percent-prompt-summary.tsv` as output. The evidence verifier recomputes timing and process arithmetic and replays all 360 default traces through the production `wsh profile report` parser.
