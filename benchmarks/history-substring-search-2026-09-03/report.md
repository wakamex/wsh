# Bundled history substring search passes its correctness and startup gates

Wsh now provides case-insensitive substring history search on the active keymap without requiring Oh My Zsh or a separately installed plugin. The bundled default added 3.427 ms at p90 over the same candidate with the feature disabled, below the fixed 4 ms gate. It was 0.649 ms slower than loading and binding the same upstream source directly. When `.zshrc` had already loaded a recognized copy, Wsh replaced its runtime definitions for 2.746 ms over the pre-change external-plugin path, below the fixed 6 ms compatibility gate.

The PTY fixture exercised actual Up and Down input through ZLE. It verified newest and older matches, forward navigation, no-match behavior, documented configuration, exact upstream and Oh My Zsh takeover, modified implementation preservation, custom binding preservation, explicit disablement, and composition with the pinned autosuggestions and syntax-highlighting sources. The process trace found no executable launched during the search interval and no comparison helper during recognized takeover.

## Startup results

Each variant ran 5 warmups followed by 20 forward-order and 20 reverse-order launches pinned to CPU 0. Timing began before PTY creation and ended at the first editable prompt.

| Build and configuration | Median, ms | p90, ms | Maximum, ms | Relevant p90 difference |
|---|---:|---:|---:|---:|
| Baseline without plugin | 6.803 | 6.984 | 7.740 | Base |
| Baseline with upstream plugin and bindings | 9.391 | 9.869 | 10.546 | +2.886 vs baseline without plugin |
| Candidate with default disabled | 6.929 | 7.092 | 7.904 | Base |
| Candidate bundled default | 9.528 | 10.518 | 10.870 | +3.427 vs candidate disabled; +0.649 vs direct upstream |
| Candidate replacing recognized upstream plugin | 11.576 | 12.615 | 13.384 | +2.746 vs pre-change external path |

The normal and compatibility paths pass their predeclared p90 thresholds. The retained process trace contains startup and cleanup processes but no `search` row. Clean and recognized-external startup each executed `wsh`, Zsh, `wsh-runtime`, and the expected asynchronous Git scan. Recognition used no `sha256sum`, `cmp`, or other helper process.

The canonical glibc 2.28 build then repeated the Rust, relocated-bundle, provider, PTY runtime, startup-configuration, history-search, dynamic-library, and imported-symbol checks. Floor bundle `46f77f0ed5297c941dbffe182aba5be695a4de5e597eaeca0cd000c231734f8b` passed with `GLIBC_2.28` as its newest imported symbol.

## Exact ownership and binding behavior

The release payload retains the upstream source byte for byte at commit `14c8d2e0ffaee98f2df9850b19944f32546fdea5` and precompiles it with the bundled Zsh. Wsh loads it after `.zshrc`, honors the upstream configuration parameters, and binds the terminal's advertised Up and Down keys in the active `main` keymap only when the existing bindings have ordinary history behavior. A custom binding remains in place.

If `.zshrc` defined both plugin widgets, Wsh identifies their common source through `functions_source`. A regular 29,692-byte source is read in one bounded `sysread` and compared exactly with the pinned upstream and Oh My Zsh reference files. A match removes the old plugin's temporary highlight hooks and reloads the precompiled Wsh copy, leaving one runtime owner. An unknown or modified implementation stays active with `WSH_HISTORY_SUBSTRING_SEARCH_OWNER=external-unknown`. `WSH_DISABLE_HISTORY_SUBSTRING_SEARCH=1` disables the default.

This does not edit `.zshrc`. A recognized plugin declaration still incurs its original source-time cost before Wsh replaces runtime ownership. A later doctor result can identify that declaration as safely removable.

## Rejected startup paths

The initial adapter loaded the upstream source inside a helper and guarded eight bindings across the `emacs` and `viins` maps. It added 7.336 ms at p90 over disabled and missed the 4 ms gate. Profiling attributed 5.36 ms to those bindings. Loading at top level, limiting binding to the active map and terminfo keys, and precompiling the source brought the normal path under the original gate.

The first recognized-copy path started `sha256sum` and added 7.825 ms over the pre-change plugin. A byte-at-a-time Zsh `read` path was slower. A 10,000-iteration probe measured one 29,692-byte `sysread` at about 0.028 ms per file and `read` at about 13.81 ms per file. The accepted path uses the bulk builtin and exact equality.

## Reproduction

```sh
tests/history-substring-search.zsh target/release/wsh <bundle> <history-substring-search-checkout> <oh-my-zsh-checkout> <autosuggestions-checkout> <syntax-highlighting-checkout> candidate

benchmarks/benchmark-history-substring-search-startup.zsh <output.tsv> target/release/wsh <bundle> <history-substring-search-checkout> candidate 0

benchmarks/trace-history-substring-search-processes.zsh <processes.tsv> target/release/wsh <bundle> <history-substring-search-checkout>

benchmarks/summarize-history-substring-search.zsh <baseline.tsv> <candidate.tsv> <summary.tsv>
```

Each checkout must contain the revision recorded in `metadata.txt`; the harness archives committed source and excludes working-tree changes. Raw samples, the deterministic summary, process rows, bundle identities, payload digests, and fixture revisions are retained beside this report.
