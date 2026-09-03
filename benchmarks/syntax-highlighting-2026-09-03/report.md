# Deferred loading fixes silent syntax-highlighting failure and improves clean startup

Wsh now provides syntax highlighting without requiring Oh My Zsh or a separately installed plugin. An ordinary direct plugin declaration in Wsh's nested startup path ran before ZLE was active, defined the plugin functions, and installed no redraw hooks. The bundled default defers the pinned upstream implementation until the first prompt, when ZLE is ready. It produced working highlighting at 29.260 ms first-editable p90, 3.155 ms faster than the 32.416 ms correctly initialized direct-upstream control.

The benchmark pinned `zsh-users/zsh-syntax-highlighting` commit `2fc57d63067c18b1100ecdbf684fa5baf49459d1`, ran the upstream test suite against both the checkout and bundled runtime files, exercised actual ZLE input and terminal output, and compared direct loading with the precompiled Wsh component. The retained correctness fixture also covers exact-copy takeover, modified and custom implementations, configuration, existing hooks, and composition with history substring search and autosuggestions.

## Startup results

Startup used 5 warmups per variant followed by 20 forward-order and 20 reverse-order launches pinned to CPU 0. Variants were interleaved within each block to control host drift. Timing began before PTY creation and ended at the first editable prompt.

| Build and configuration | First-editable p90, ms | Difference from relevant control, ms | Result |
|---|---:|---:|---|
| Baseline without syntax highlighting | 27.282 | - | Startup control |
| Baseline ordinary upstream source | 31.832 | +4.550 | Reproduced silent no-hook state |
| Baseline upstream source after loading ZLE | 32.416 | - | Working direct-upstream control |
| Candidate with default disabled | 27.285 | +0.003 | Passed 0.25 ms disabled gate |
| Candidate bundled default | 29.260 | -3.155 | Passed 1 ms clean-path gate |
| Candidate activating an exact inactive copy | 34.521 | +2.105 | Passed 3 ms compatibility gate |
| Candidate preserving an exact active copy | 33.824 | +1.409 | Passed 3 ms compatibility gate |

The ordinary external row is not a performance control because it did no highlighting. The clean bundled path is the normal Wsh result. The two coexistence paths retain the user's source-loading work and add exact in-process file comparisons so Wsh can distinguish a known inactive copy from modified or custom code without taking ambiguous ownership.

The exact-copy gate began at 1 ms. Comparing all shipped runtime files cost about 3.5 ms. Restricting the startup check to the core file and active highlighter files reduced the retained difference to 2.105 ms while still proving ownership of every function Wsh activates. A native module, helper process, or recognition cache would add machinery for a transitional redundant declaration that a later doctor result can recommend removing, so the accepted compatibility budget is 3 ms. The clean and disabled gates did not change.

## Redraw results

Each path used 10 warmups followed by 100 retained redraws for a short valid command and a 1,000-byte buffer. Timing began before the test widget replaced the buffer and ended after an observer ran following the syntax hook.

| Build and configuration | Short redraw p90, ms | 1,000-byte redraw p90, ms |
|---|---:|---:|
| Baseline working direct upstream | 13.551 | 13.624 |
| Candidate bundled default | 13.566 | 13.629 |
| Candidate exact-copy activation | 13.524 | 13.612 |

Every candidate result stayed within 0.2 percent of the corresponding direct-upstream p90 and passed the fixed limit of no more than 20 percent overhead. The PTY harness polling interval dominates these absolute values, so the matched comparison establishes no material regression rather than isolated plugin compute time.

The traced edit window created no process and executed no program. The complete successful session ran only `taskset`, `wsh`, Zsh, `wsh-runtime`, and the expected Git provider scans. Exact-copy recognition therefore adds no checksum or comparison helper.

## Correctness and ownership

The retained PTY fixture verifies command, missing-command, quoted-argument, and path regions through actual ZLE redraws. It confirms one redraw hook, one finish hook, one pre-exec hook, and preservation of a pre-existing custom redraw hook. The configured `main` and `brackets` highlighters and custom style values remain effective. History substring search, autosuggestions, and syntax highlighting retain one owner each while the suggestion suffix and syntax regions remain visible together.

Wsh vendors the upstream runtime files byte for byte and precompiles them with the paired Zsh. The adapter loads after `.zshrc`. When no implementation exists, it defers the bundled source until ZLE is active. When the exact core and every active shipped highlighter match, Wsh either preserves already installed hooks or installs the missing upstream hooks around those functions without parsing a second copy. Modified active files, custom active highlighters, incomplete installations, and unknown implementations remain external.

`WSH_DISABLE_SYNTAX_HIGHLIGHTING=1` disables the default. Upstream `ZSH_HIGHLIGHT_HIGHLIGHTERS` and `ZSH_HIGHLIGHT_STYLES` configuration remains available before Wsh loads.

Wsh does not edit `.zshrc`. A recognized redundant plugin declaration still pays its source and exact-recognition cost before takeover. A later doctor result can compare the complete installation outside startup and identify declarations that are safe to remove.

## Reproduction

```sh
tests/syntax-highlighting-upstream.zsh <bundle> <syntax-highlighting-checkout> <output.log>

tests/syntax-highlighting.zsh target/release/wsh <bundle>

benchmarks/benchmark-syntax-highlighting-startup.zsh <output.tsv> target/release/wsh <baseline-bundle> <candidate-bundle> <syntax-highlighting-checkout> 0

benchmarks/benchmark-syntax-highlighting-edit.zsh <output.tsv> target/release/wsh <bundle> <syntax-highlighting-checkout> baseline|candidate 0

benchmarks/trace-syntax-highlighting-edit.zsh <output-directory> target/release/wsh <bundle> <syntax-highlighting-checkout> 0

benchmarks/summarize-syntax-highlighting.zsh <startup.tsv> <edit-baseline.tsv> <edit-candidate.tsv> <summary.tsv>
```

The checkout must contain the revision recorded in `metadata.txt`; the harness archives committed source and excludes working-tree changes. Raw timing samples, deterministic summary, upstream-suite output, process evidence, exact bundle identities, source and payload digests, and floor-build result are retained beside this report.
