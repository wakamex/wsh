# Pinned edge Zsh passes the complete Wsh gates

Wsh can adopt upstream Zsh commit `cad0d67c76e2be7371cf3526b79ea2581810d35a`. The candidate passed the upstream and complete Wsh correctness suites, stayed within every fixed startup, prompt, process, repaint, tracing, and retained-memory gate, and supplied tested post-5.9 features. Stable Zsh 5.9.2 and the candidate were built as complete x86-64 glibc 2.28 bundles with the same Wsh source, Rocky package lock, Rust toolchain, GCC 8.5 compiler, build settings, fixtures, and instrumentation.

The unchanged candidate initially took about 521 ms to initialize Wsh instead of 10 ms because post-5.9 ZLE queries the terminal by default and waits 500 ms when no reply arrives. Wsh now sets the documented `-query` terminal extension before `.zshrc` for this exact revision unless the user supplied a terminal policy in the environment or `.zshenv`. The final managed first-editable p90 was 29.660 ms on edge versus 28.772 ms on stable, a 0.889 ms regression within the fixed 1.0 ms limit. Raw first-editable p90 changed by 0.006 ms.

## Acceptance summary

| Gate | Stable | Edge | Limit | Result |
|---|---:|---:|---:|---|
| Raw process startup p90 | 1.830 ms | 1.866 ms | Edge regression at most 1.0 ms | Pass, +0.036 ms |
| Raw first-editable p90 | 5.146 ms | 5.153 ms | Edge regression at most 1.0 ms | Pass, +0.006 ms |
| Direct complete-Wsh first-editable p90 | 29.228 ms | 28.619 ms | Edge regression at most 1.0 ms | Pass, -0.609 ms |
| Managed complete-Wsh first-editable p90 | 28.772 ms | 29.660 ms | Edge regression at most 1.0 ms | Pass, +0.889 ms |
| Minimal worst updated-state p90 added over raw | 6.805 ms | 6.840 ms | At most 7.1 ms | Pass |
| Minimal worst updated-state maximum added over raw | 7.038 ms | 7.095 ms | At most 8.0 ms | Pass |
| Wakamex worst updated-state p90 added over raw | 6.685 ms | 6.860 ms | At most 7.1 ms | Pass |
| Wakamex worst updated-state maximum added over raw | 7.022 ms | 7.190 ms | At most 8.0 ms | Pass |
| All interactive defaults first-editable p90 | 28.872 ms | 29.313 ms | Edge regression at most 1.0 ms | Pass, +0.442 ms |
| Short syntax-highlight redraw p90 | 1.520 ms | 1.531 ms | At most 20 percent regression | Pass, +0.7 percent |
| 1,000-byte syntax-highlight redraw p90 | 10.237 ms | 10.846 ms | At most 20 percent regression | Pass, +5.9 percent |
| Complete Wsh retained PSS p90 | 3,563 KiB | 3,582 KiB | Added PSS at most 4,096 KiB | Pass, +19 KiB total |
| Git processes per changed transition | 1 | 1 | At most 1 | Pass |
| Git processes without `GIT_OPTIONAL_LOCKS=0` | 0 | 0 | 0 | Pass |
| Repaints per changed result | 1 | 1 | At most 1 | Pass |
| Timed clean, dirty, and untracked semantic checks | 240/240 | 240/240 | 100 percent | Pass |
| Untimed staged and detached-HEAD checks | 8/8 | 8/8 | 100 percent | Pass |

[`summary.tsv`](summary.tsv) contains all retained medians, nearest-rank p90 values, maxima, sample counts, and units. The minimal and Wakamex provider figures above subtract each renderer's matched raw control by state. Trace overhead depends only on `wsh-runtime`; the two bundles contain the byte-identical runtime SHA-256 `c87a118f9303e29447b1d20ee39f81565a3fc904a25098b3da720e68ed355026`, so the accepted 1.533 ms runtime-ready and 0.190 ms refresh p90 overhead remains the applicable measurement rather than a Zsh-source variable.

## Source and upstream tests

The candidate source lock records canonical repository, commit, tree, and archive identities:

- Repository: `https://github.com/zsh-users/zsh`
- Commit: `cad0d67c76e2be7371cf3526b79ea2581810d35a`
- Tree: `2c07cbc91c766336de8029e0da8e34723bbe09bf`
- Archive SHA-256: `79120ee69dde051792ec548817126381331f26a7131244aab17d4d2cbb5b1819`
- Reported version: `5.9.999.3-test`
- Linear context: 1,074 commits on `master` after Zsh 5.9; Zsh 5.9.2 is on a diverged maintenance branch

Git snapshots do not include generated `configure` or manual files. The candidate build runs upstream `Util/preconfig`, then installs only the executable, modules, and functions that enter the Wsh payload. It does not generate or ship Zsh documentation.

The unchanged candidate suite reported five failures in `A02alias`, `B06fc`, `D04parameter`, `K01nameref`, and `W01history`. Source inspection isolated all five to upstream test commit `41ba309de08b5b1816c2d24bdbe449c2760a6974`, which attempted to suppress interactive prompts with command-prefix `PS1=` assignments. Both the candidate and stable 5.9.2 emit prompts for those invocations. The digest-pinned patch `e5f79c067b6cf470f2f9ee40d821eb1dc2c188efed00ab32d3a7e2d20483f4b7` changes only those `Test/` fixtures, retains every test, and never changes compiled or installed source. The corrected candidate suite passed 75 scripts with 0 failures and 2 existing skips. The stable control passed 63 scripts with 0 failures and 2 existing skips. The raw transcripts are in [`zsh-upstream-edge.log`](zsh-upstream-edge.log) and [`zsh-upstream-stable.log`](zsh-upstream-stable.log).

## Terminal-query compatibility rule

Post-5.9 ZLE initializes `.term.extensions` by querying the terminal. Its `.term.querywait` default is 50 hundredths of a second. The benchmark PTY did not answer, producing repeatable 520.7 to 521.6 ms integrated load times while stable loaded in 9.6 to 10.1 ms. Setting `.term.extensions=(-query)` before ZLE initialization reduced the candidate load to 9.890 ms in the one-factor counterfactual.

The accepted rule runs in the managed `.zshenv` after the user's `.zshenv` and before `.zshrc`, plus the direct integration entrypoint. It applies only when `ZSH_VERSION` is `5.9.999.3-test`, `WSH_ENABLE_ZLE_TERMINAL_QUERY` is not `1`, and `.term.extensions` is still undefined. This lets an environment or `.zshenv` policy opt into queries or supply explicit extensions, while preventing a plugin in `.zshrc` from loading ZLE before the safe default. The floor suite checks the default and preservation of an explicit user value.

The first managed-startup measurement inherited the host `.zshrc`, mixed about 700 ms of unrelated configuration into both builds, and let that configuration initialize edge ZLE before the original `.zshrc`-level rule. [`first-editable-host-config-invalid.tsv`](first-editable-host-config-invalid.tsv) is retained as the rejected precursor. The accepted harness supplies identical empty user startup directories and led to the earlier `.zshenv` placement.

## Interactive defaults and ZLE

The full bundle suite passed existing startup ordering, changed `ZDOTDIR`, `RCS`, user hooks, runtime lifecycle, job control, hostile values, cancellation, crash fallback, and plugin coexistence tests on both builds. Separate retained PTY logs cover actual substring-history Up and Down navigation, visible and accepted autosuggestions, cancellation, custom widget preservation, syntax regions, custom styles, and composition of all three defaults.

The paired startup matrix independently enabled none, history search, autosuggestions, syntax highlighting, and all three defaults. Edge p90 changes ranged from +0.119 to +0.442 ms. Autosuggestion settled-prompt p90 changed by at most 0.087 ms; visible-suggestion and acceptance p90 values were slightly lower on edge.

The existing syntax benchmark's external file observer polls every 10 ms. A scheduling shift placed 53 of 200 edge short-buffer samples into the next polling bucket versus 6 stable samples, even though medians remained about 1.85 ms. The accepted source comparison records elapsed time inside ZLE from the buffer-changing widget through the post-highlight hook. It measured 1.520 versus 1.531 ms p90 for the short buffer and 10.237 versus 10.846 ms for 1,000 bytes. Both Wsh-owned and direct-upstream paths showed the same outer-observer behavior, so no compatibility intervention was added.

## Tested post-5.9 value

The targeted feature fixture verified four capabilities unavailable in the stable control:

- Current-shell command substitution captures output while preserving assignments in the current shell process.
- `zsh/ksh93` named references update caller-owned values.
- `.zle.hlgroups` and `layer=` accept named layered highlight composition.
- `ZSH_EXEPATH` reports the exact bundled Zsh executable.

These features support lower-process shell glue, structured state handoff, future highlight composition, and exact bundle self-identification. The fixture does not claim coverage for every item in upstream `NEWS`.

## Bundle size and identity

| Property | Stable | Edge | Difference |
|---|---:|---:|---:|
| Bundle identity | `23806d05c2ee5ecac62414059ba5cc09a8f4d447ab3992e60f041051cf8d97dc` | `d5597552d6844f954065ff7154a1b479dd52600f0d5f50600b889615b5dbc99c` | - |
| Zsh binary SHA-256 | `bac80fcae8e1dd2aa1d5b77d5a68a7bb73612f8bf349d1f33e775117b7cd5cfb` | `a902861ceae7cf1bc545fd0f3b0a3cfdb901c9d38e728886940e044de7efff48` | - |
| Unpacked bytes | 9,343,271 | 9,396,578 | +53,307 |
| Compressed archive bytes | 2,466,836 | 2,488,224 | +21,388 |
| Archive SHA-256 | `a8a20437f013638ecf6fa193f2f9e10dc3e82c4dba54e5089c35ecb84fcceaff` | `dffb0b1b228f45319267c3dc2f3b65cf2668da28c6da2999a93030b517c476c1` | - |
| Newest imported glibc symbol | `GLIBC_2.28` | `GLIBC_2.28` | None |

Both bundles identify Wsh source `6169380bdb0d4919ccb424885b5f194dbb9fc786+dirty`, package lock SHA-256 `01128ba43dbd94d3218f64f03e7ed5ea56d69ce875dd86a2c7b074aac51d0c44`, path-independent Rust toolchain SHA-256 `a7e4e0e9ff4ed572a30fa9c49d347b01b81d1fa1a80cd00ea585939ac62b7e61`, Rust 1.95.0, GCC 8.5.0, and GNU ld 2.30. They are unsigned development artifacts. A release still requires a clean tagged revision, two byte-identical canonical builds, attestations, and the full release workflow.

## Method and retained evidence

The controlled host was an AMD Ryzen 9 3950X running Fedora kernel 7.1.9. Startup and edit workloads were pinned to CPU 31. Raw process startup used 5 forward and 5 reverse observations of 5,000 launches per build. First-editable and default-startup comparisons used 5 warmups followed by 20 forward and 20 reverse samples per variant. Provider runs used the calibrated `zsh-theme-bench` PTY harness with 20 clean, dirty, and untracked transitions per target in stable-edge-edge-stable order, plus staged and detached-HEAD checks. Syntax and autosuggestion edit paths used 100 retained samples per configuration. Memory used 20 paired sessions after 20 prompt warmups and 250 ms idle settling.

The experiment used one host, one x86-64 glibc target, and the existing 1,000-file repository fixture. This is enough for the current Linux bundle decision, not a compatibility claim for untested platforms, terminals, or arbitrary configuration. [`metadata.txt`](metadata.txt) records commands and identities, and [`summary.tsv`](summary.tsv) is reproduced by [`../summarize-edge-zsh.zsh`](../summarize-edge-zsh.zsh).
