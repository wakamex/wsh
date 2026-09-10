# Native history ownership passes installed editor and startup gates

C now owns history search state, matching, duplicate filtering, navigation, cursor updates and search highlights. The installed implementation passes 110 paired real-editor comparisons against the pinned plugin in both normal and ASan/UBSan builds, plus all nine existing installed integration suites. Its 10,000-entry editing sequence is 22.7% faster in default mode and 72.3% faster with uniqueness enabled. Fifty alternating pairs per workload measure the complete sequence, including display handling.

| History entries and mode | Pinned plugin median, ms | Installed C owner median, ms | Median reduction | Paired p95 change, ms |
| --- | ---: | ---: | ---: | ---: |
| 100, default | 6.398 | 5.600 | 12.5% | -0.555 |
| 100, unique | 7.544 | 5.644 | 25.2% | -1.640 |
| 10,000, default | 11.032 | 8.526 | 22.7% | -2.183 |
| 10,000, unique | 238.097 | 65.840 | 72.3% | -166.676 |

Every editing workload passes the +1 ms paired-p95 non-regression gate; the large unique workload passes the fixed 20% reduction gate. Independent default startup checks also pass the +3 ms paired-p95 gate: -0.248 ms with the existing prompt and +0.850 ms with the minimal prompt. These results select the native history owner in native development builds. Published legacy releases are unchanged.

## Ownership and compatibility

Public configuration and widget registration remain a small Zsh adapter. Zsh owns the editor, native history, widget dispatch and multiline movement; the existing syntax highlighter retains its rendering authority. The C owner invokes these existing facilities and owns its own query, result, raw-history keys and duplicate set without exporting the old internal search parameters. The adapter retains highlighter ordering and standalone cleanup. The full pinned plugin remains in the payload as the recognized-copy comparison reference and for the legacy build path.

Actual-editor comparisons cover buffer bytes, cursor position and displayed search regions, Unicode, multiline movement, custom widgets, emacs/vi configuration, fuzzy search, unique results, HIST_IGNORE_ALL_DUPS, HIST_FIND_NO_DUPS, prefix matching, case sensitivity and disabled syntax highlighting. The existing integration suite checks recognized upstream/OMZ replacement, unknown implementations, custom bindings and suggestion/highlight composition. During integration, the tests caught an accidental rename of literal highlight identifiers; the corrected source passed normal and sanitizer reruns before timing.

## Reproduction and retained evidence

`inputs.tar.gz` binds the final native implementation, adapters, source lock, installed manifest and test harnesses; it also preserves the earlier module prototype's source for its retained comparison. `results.tar.gz` includes generated fixtures, raw PTY transcripts, all measurements, normal and sanitizer comparisons, the integration suite, and the final host upstream-build log. `identity.json` identifies the unsigned installation and both shell binary hashes. This is host qualification, not a fresh canonical glibc-floor or release qualification.

Run `python3 native/test-history-owner.py BUNDLE/bin/wsh installed OUTPUT correctness`, followed by the same command with `measure`. The pinned plugin in the repository is the control; both variants run in the same installed shell, and timing shells use CPU 0 with tracing off. Run `python3 native/check-installation.py BUNDLE OUTPUT` for the nine existing integration suites. Run `python3 native/measure-startup.py CONTROL_BUNDLE BUNDLE OUTPUT` against completion-only installation `376c2e4803daf7b394d35d26a8c552b909005924c76f8b2513ed93562a576aeb` for 50 paired startup samples per prompt mode.

Sanitized checks use the same private installed fixture method and compiler settings documented in the completion report. The reference highlighter timeout is zero in editor measurements, avoiding an intentional wait for user input while retaining redraw and highlight cleanup work. `benchmarks/verify-native-history-adoption.py` independently recalculates the retained editor and startup gates and checks source identities.
