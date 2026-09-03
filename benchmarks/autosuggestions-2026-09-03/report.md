# Bundled autosuggestions remove repeated prompt rebinding without slowing editing

Wsh now provides history-based inline suggestions without requiring Oh My Zsh or a separately installed plugin. The bundled default cut settled no-op prompt p90 from 20.698 ms with upstream automatic rebinding to 10.545 ms by selecting upstream's documented manual-rebind mode. Suggestion display and acceptance remained effectively equal to the direct upstream manual path: 10.319 ms versus 10.326 ms p90 to display a warm history suggestion, and 1.952 ms versus 1.958 ms to accept it.

The benchmark pinned `zsh-users/zsh-autosuggestions` commit `85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5`, exercised real input and terminal output through ZLE, and compared the same source loaded from `.zshrc` with its precompiled Wsh bundle copy. A PTY correctness fixture separately covered suggestion behavior, cancellation, configuration, plugin ownership, history search, custom widgets, explicit rebinding, and syntax-highlighting composition.

## Startup and settled-prompt results

Startup used 5 warmups followed by 20 forward-order and 20 reverse-order launches pinned to CPU 0. Timing began before PTY creation and ended at the first editable prompt. The settled benchmark used 10 warmups and 200 retained no-op prompt transitions in each long-lived shell.

| Build and configuration | First-editable p90, ms | Settled-prompt p90, ms | Relevant result |
|---|---:|---:|---:|
| Baseline without autosuggestions | 10.718 | 10.541 | Startup control |
| Baseline upstream automatic rebinding | 24.595 | 20.698 | Rebinding cost control |
| Baseline upstream manual rebinding | 25.137 | 10.552 | Documented upstream counterfactual |
| Candidate with default disabled | 10.747 | 10.541 | +0.029 ms startup versus baseline control |
| Candidate bundled default | 24.073 | 10.545 | -0.522 ms startup versus upstream automatic; 49.1 percent lower settled p90 |
| Candidate replacing a recognized pending copy | 26.181 | 10.543 | +1.586 ms startup versus the pre-change external path |

The clean bundled path passed its fixed startup gate of no more than 1 ms over the direct upstream component. Recognized takeover passed its 4 ms compatibility gate, and the disabled adapter passed its 0.25 ms gate. Manual rebinding exceeded the required 20 percent settled-prompt improvement.

## Warm suggestion results

Each path used 10 warmups and 100 retained interactions. Availability timing began before writing the history prefix and ended when the expected suggestion suffix appeared in terminal output. Acceptance timing began before Ctrl-E and ended when a ZLE reporter observed the complete buffer.

| Build and configuration | Suggestion available p90, ms | Full acceptance p90, ms |
|---|---:|---:|
| Baseline upstream manual rebinding | 10.326 | 1.958 |
| Candidate bundled default | 10.319 | 1.952 |
| Candidate replacing a recognized pending copy | 10.332 | 1.954 |

Both candidate paths passed the fixed limit of no more than 20 percent over upstream. The availability values include the PTY harness's polling resolution, so the matched-path differences are more useful than treating 10 ms as the plugin's isolated compute time.

One traced keystroke created one short-lived Zsh worker, which exited and was reaped before the suggestion became visible. The edit window contained no `execve`. The complete traced session successfully executed only `taskset`, `wsh`, Zsh, `wsh-runtime`, and the expected Git provider scans. Exact-plugin recognition therefore launched no checksum or comparison helper.

## Correctness and ownership

The retained PTY fixture verified visible history suggestions, complete acceptance, newest and older substring-history navigation, forward navigation, ordinary edits, Ctrl-C cleanup, a custom widget, an explicitly rebound later widget, disablement, configuration, and composition with pinned `zsh-syntax-highlighting`. Cancellation left no live suggestion worker, registered descriptor, or visible suffix.

The release payload retains the upstream distribution source byte for byte and precompiles it with the paired Zsh. Wsh loads its adapter after `.zshrc`. An exact upstream copy that has only registered its pending first-prompt hook is removed and replaced by the bundled copy. A copy that already wrapped widgets remains the active external owner because unwinding its wrapper stack would be ambiguous. Modified or unknown implementations also remain external.

The default sets upstream's `ZSH_AUTOSUGGEST_MANUAL_REBIND` before the first prompt. Widgets that exist when Wsh loads are wrapped once. Code that adds or replaces a relevant widget later calls `_zsh_autosuggest_bind_widgets` explicitly, which the fixture verifies. `WSH_AUTOSUGGEST_REBIND_MODE=automatic` restores upstream's per-prompt scan, `WSH_AUTOSUGGEST_ASYNC=0` selects synchronous fetching, and `WSH_DISABLE_AUTOSUGGESTIONS=1` disables the bundled default. Upstream style, strategy, buffer, completion, and widget-list configuration remains available before Wsh loads.

Wsh does not edit `.zshrc`. A recognized redundant plugin declaration still pays its source-time cost before takeover. A later doctor result can identify that declaration as safely removable.

## Reproduction

```sh
tests/autosuggestions.zsh target/release/wsh <bundle> <autosuggestions-checkout> <syntax-highlighting-checkout>

benchmarks/benchmark-autosuggestions-startup.zsh <output.tsv> target/release/wsh <bundle> <autosuggestions-checkout> baseline|candidate 0

benchmarks/benchmark-autosuggestions-prompt.zsh <output.tsv> target/release/wsh <bundle> <autosuggestions-checkout> baseline|candidate 0

benchmarks/benchmark-autosuggestions-edit.zsh <output.tsv> target/release/wsh <bundle> <autosuggestions-checkout> baseline|candidate 0

benchmarks/trace-autosuggestions-edit.zsh <output-directory> target/release/wsh <bundle> <autosuggestions-checkout> 0

benchmarks/summarize-autosuggestions.zsh <startup-baseline.tsv> <startup-candidate.tsv> <prompt-baseline.tsv> <prompt-candidate.tsv> <edit-baseline.tsv> <edit-candidate.tsv> <summary.tsv>
```

Each checkout must contain the revision recorded in `metadata.txt`; the harness archives committed source and excludes working-tree changes. Raw timing samples, the deterministic summary, process evidence, exact bundle identities, source and payload digests, and floor-build result are retained beside this report.
