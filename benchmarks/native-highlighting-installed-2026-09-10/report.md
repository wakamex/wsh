# Installed C main highlighting cuts redraw time by 35–91%

Native development builds now select the complete C main highlighter. The installed implementation passes 287 upstream fixtures, 3,360 actual-style typing-prefix comparisons, sanitizer checks and the canonical glibc 2.28 suite. Across 50 alternating pairs, complete redraw medians improve 35–91%, with essentially unchanged startup readiness.

| Complete redraw workload | Original main highlighter median | Installed C main highlighter median | Median reduction | Paired p95 candidate minus control |
|---|---|---|---|---|
| Short command | 2.123 ms | 1.378 ms | 35.1% | -0.387 ms |
| 100 repeated commands | 119.652 ms | 11.203 ms | 90.6% | -101.722 ms |
| 100 distinct defined commands | 127.059 ms | 15.955 ms | 87.4% | -102.161 ms |
| Multiline conditional with expansion | 5.030 ms | 1.549 ms | 69.2% | -2.746 ms |

| First-editable readiness | Pre-port native installation median | C-highlighting installation median | Paired p95 candidate minus control | Fixed regression limit |
|---|---|---|---|---|
| Existing user prompt | 15.583 ms | 15.381 ms | +0.038 ms | +3 ms |
| Minimal Wsh prompt | 17.712 ms | 17.510 ms | +0.013 ms | +3 ms |

## Selected ownership

`native/highlight.c` owns the complete main parser and helpers. Zsh startup registers its builtin directly; there is no runtime-loaded module in the installed path. One shell adapter invokes that builtin per redraw. Token iteration, parser state, aliases, quotes, recursive substitutions, paths, fallback and ordered region emission remain inside C. The old interpreted main parser and its command-cache hook are absent when the bundled main highlighter is selected.

The existing upstream redraw lifecycle, style configuration and separately selectable highlighters remain available. External exact, modified and custom implementations retain their existing ownership and hooks. Thus users who explicitly source an external highlighter continue using that implementation; the measured gains apply to Wsh's bundled main highlighter. Doctor continues to identify redundant exact declarations.

Assembly generates the main configuration/predicate adapter and retains the byte-exact original main source as `known-main-highlighter.zsh`. Recognition accepts either the shipped adapter or the original reference and rejects modified copies. The coexistence test verifies native parser selection, absence of the old parser and preserved user hook order. The removed cache hook is deliberately absent from the expected native hook list.

The native implementation caps recursive substitution parsing at 128 levels and processing at 100,000 token iterations per command-list parse. These bounds limit work on extreme input. The normal editor workloads and authoritative fixtures remain within those bounds.

## Qualification

| Check | Result |
|---|---|
| Authoritative upstream highlighter corpus | 287/287 for both original and installed native owners |
| ASan/UBSan highlighter corpus | 287/287 for both owners; no diagnostics |
| Actual-style typing prefixes under seven option configurations | 3,360/3,360 exact matches in normal and sanitized shells |
| Highlighted command-substitution markers | No input executed |
| Main, brackets and selected native autosuggestions in real ZLE | Exact ordered regions for all four workloads in normal and sanitized shells |
| Installed main lifetime | 0 KiB retained growth over 4,000 redraws after a 2,000-redraw warmup |
| Canonical glibc 2.28 main lifetime | 0 KiB retained growth over the same batches |
| Host installed contracts | All nine pass, including exact/modified/custom ownership, doctor, real OMZ prompt and directory integration, and foreground jobs |
| Host and canonical upstream Zsh tests | 75 scripts, zero failures, two platform skips |
| Canonical native installation and RPM | Manifest, highlighting, autosuggestions, recovery, profile, completion, history, directory, runtime lifecycle and RPM checks pass |

The early installed-contract failures were in recognition and expectations, not parser parity: the doctor fixture sourced the generated native adapter while recognition compared only the original, and the coexistence fixture still required the removed main cache hook. Both failed runs are retained. Recognition now accepts both known sources, and the hook-order assertion preserves the remaining exact order.

## Reproduction and evidence

The [plan](plan.md) records the installed gates. The [preceding experiment](../native-highlighting-full-2026-09-10/report.md) retains the independent identical-control and observer-overhead measurements and the allocation-lifetime correction. Installed timing uses the same instrumentation and 50 alternating pairs on CPU 0, with exact composed-region equality required for every pair. No timing samples were excluded or overhead subtracted. Startup uses the native primary editable OSC 133 marker with tracing disabled and both prompt owners.

`identity.json` records source hashes, shell identities and archive contents. `evidence.tar.gz` retains normal and sanitizer corpus logs, actual-style comparisons, editor transcripts, paired timings, startup samples, lifetime results, all host contracts, canonical checks and exact build commands. The initial installed corpus used a shell byte-identical to the final host shell; only the adapter recognition changed between those installation inventories. The sanitizer fixture replaces the shell in a copied development layout and is explicitly nondistributable. No host installation, push or release was performed.

```sh
python3 native/test-installed-highlighting.py INSTALLATION OUTPUT
python3 native/prepare-highlight-full.py UPSTREAM_CHECKOUT installed CORPUS_FIXTURE
python3 native/test-highlight-parser.py INSTALLATION/bin/wsh CORPUS_FIXTURE CORPUS_OUTPUT
python3 native/test-highlight-traversal-zle.py INSTALLATION/bin/wsh OUTPUT/fixture OUTPUT/editor measure
python3 native/measure-startup.py PRE_PORT_INSTALLATION INSTALLATION STARTUP_OUTPUT
./build/build-glibc-2.28-development-bundle.zsh
python3 benchmarks/verify-installed-highlighting.py
```
