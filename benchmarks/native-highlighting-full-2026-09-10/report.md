# Complete C main highlighting passes compatibility and cuts redraw time

The complete C main highlighter removes the per-token shell interface and reduces complete redraw medians by 32–91%. It passes all 287 authoritative upstream fixtures, 3,360 typing-prefix comparisons of actual styles, normal and ASan/UBSan runs, and composed real-ZLE checks with brackets and native autosuggestions. Measurements use 50 alternating pairs per workload after correctness and allocation-lifetime checks.

| Complete redraw workload | Original main highlighter median | Complete C main highlighter median | Median reduction | Paired p95 candidate minus control |
|---|---|---|---|---|
| Short command | 2.117 ms | 1.431 ms | 32.4% | -0.293 ms |
| 100 repeated commands | 120.031 ms | 10.553 ms | 91.2% | -102.327 ms |
| 100 distinct defined commands | 128.636 ms | 15.192 ms | 88.2% | -103.498 ms |
| Multiline conditional with expansion | 5.143 ms | 1.574 ms | 69.4% | -2.759 ms |

## Ownership and compatibility

The native implementation owns the main highlighter's command state, delimiter stack, precommands, aliases, safe parameter inspection, assignments, redirections, paths, quoting, nested command/process/arithmetic substitutions, backtick offset mapping, style fallback and ordered region emission. It calls Zsh's native lexer and parameter tables directly. One builtin invocation processes an entire redraw; it does not call an interpreted parser, shell helper or interpreter from its token loop.

The original main parser and helpers are absent from the candidate fixture. The pinned shell lifecycle and separately selectable brackets, cursor, line, pattern and regexp highlighters remain in Zsh. This experiment completes main-parser ownership, not replacement of every optional highlighter or the plugin's redraw lifecycle. The C source is approximately 1,300 lines versus 1,848 upstream main-highlighter lines, with a small generated configuration/predicate adapter. Vendored upstream bytes remain unchanged for reference and compatibility recognition.

The upstream driver normally intercepts `_zsh_highlight_add_highlight` to observe symbolic styles. The candidate's test-only symbolic mode returns the complete native fallback chain to that same observer. Fixture inputs and expected assertions are unchanged, including the inheritance fixture that inspects the entire chain. Separate differential and PTY checks compare actual ordered styles through the normal rendering path. The 3,360 prefix cases include unfinished nested syntax, Unicode, NUL/control input and seven option configurations. Marker files confirm that command substitutions in highlighted input were not executed.

## Allocation lifetime correction

Review found temporary concatenations using Zsh's permanent allocator. The original candidate retained 100,000 KiB over two 2,000-redraw batches following warmup. Moving those strings to Zsh's scoped heap reduced measured retained growth to 0 KiB across the same 4,000 redraws. Both runs and the original source/module are retained. All correctness and sanitizer checks were repeated after the fix; the table above measures the corrected module. Earlier timing from the leaking candidate is superseded.

## Measurement and reproduction

The [plan](plan.md) fixes the compatibility, regression and lifetime gates. Tracing and sanitizers are disabled during timing, CPU affinity is CPU 0, and the two owners alternate order. Every measured pair must match ordered composed regions. The timer ends at the redraw callback, before physical terminal painting. Identical-control and capture-overhead measurements are retained separately without subtracting overhead or excluding samples. The candidate passes both median and paired-tail regression limits.

`identity.json` records source revision, module and shell identities, matching SDK header hashes, compiler flags, target and every archive input. `evidence.tar.gz` contains original test checkouts, generated candidate fixtures, all final corpus logs, actual-style comparisons, editor transcripts, paired samples, sanitizer evidence and lifetime results. These are unsigned development experiments. At this experiment's commit, the module remains private; installed selection requires separate qualification.

```sh
cc -std=c17 -Wall -Wextra -Werror -O2 -fPIC -shared -I"$SDK/Src" -I"$SDK" native/highlight-full-prototype.c -o "$OUT/wshhighlightfull.so"
python3 native/prepare-highlight-full.py UPSTREAM_CHECKOUT "$OUT" FIXTURE
python3 native/test-highlight-parser.py INSTALLATION/bin/wsh FIXTURE CORPUS_OUTPUT
python3 native/test-highlight-full-differential.py INSTALLATION/bin/wsh FIXTURE DIFFERENTIAL_OUTPUT
python3 native/test-highlight-full-lifetime.py INSTALLATION/bin/wsh FIXTURE/candidate/zsh-syntax-highlighting.zsh LIFETIME_OUTPUT
python3 native/test-highlight-traversal-zle.py INSTALLATION/bin/wsh FIXTURE EDITOR_OUTPUT correctness
python3 native/test-highlight-traversal-zle.py INSTALLATION/bin/wsh FIXTURE EDITOR_OUTPUT measure
```

Repeat correctness with the sanitized shell and module using flags in the identity. For identical-control and observer overhead, point both fixture owners at the original highlighter and add `--capture-overhead` only for the latter experiment.
