# Native highlighting parser remains incomplete

The substantial C parser prototype does not meet the compatibility gate. It passes 117 of 271 main-highlighter fixtures, while the pinned reference passes all 271. The other 16 upstream fixtures pass in both variants. Normal and sanitized runs agree. Keep the existing highlighter selected; there is no qualified performance result for adopting this parser.

| Authoritative upstream fixtures | Pinned reference | C command-list parser candidate | Outcome |
|---|---|---|---|
| Main parser and highlighting semantics | 271/271 | 117/271 | 154 failures |
| Brackets, patterns and regular expressions | 16/16 | 16/16 | Unchanged providers pass |
| Complete corpus, normal build | 287/287 | 133/287 | Compatibility gate fails |
| Complete corpus, ASan/UBSan build | 287/287 | 133/287 | Same functional failures; no sanitizer diagnostics |
| Real ZLE initial redraw composition | 3 matching single-line workloads and one multiline reference | Three initial matches; multiline differs | Whole-feature gate fails |

## Implemented boundary and decision

The private C module owns command-list traversal, assignment and redirection state, precommands and basic compound delimiters. It uses Zsh's native lexical splitter and retains the existing command classifier, argument highlighters and style helpers. A generated private fixture replaces the main parser function, approximately 678 lines, with a small local-context wrapper and the C builtin. There is deliberately no fallback that could make unsupported parsing appear correct.

Failures include absolute-path command classification, aliases and alias expansion, arithmetic and command substitutions, array assignments, unfinished syntax, compound constructs and multiline region handling. The retained per-case results enumerate every failure. This boundary is substantial enough to expose the maintenance problem: tokenization alone does not supply the semantic state and source offsets that the highlighter needs.

Do not extend this prototype by patching individual fixtures until the corpus happens to pass. Further work needs a new hypothesis for obtaining complete parser state and source locations, with a bounded compatibility experiment. The current evidence supports keeping the pinned highlighter, even with a general preference for C consolidation. The private module and generator remain available for inspection and further experiments but are absent from the native source lock and installed payload.

## Redraw experiment and stopping point

The real ZLE harness composes main highlighting, bracket highlighting and autosuggestions. Initial correctness runs match a short command, 100 repeated commands and 100 distinct defined commands. The multiline `if` fixture differs in both normal and sanitized runs. No timing is accepted for that fixture.

An initial 50-pair experiment on the three matching fixtures serialized the entire buffer and region table inside the timed callback. Its recorded median reductions were 11.4%, 25.5% and 13.3%, with paired p95 deltas of -0.099 ms, +4.672 ms and +174.871 ms respectively. The latter two fail the existing +1 ms regression gate. These are diagnostic observations from an unsuitable measurement boundary, not product speed claims.

The corrected observer emits a compact nonprinting marker at the end of the composed redraw hooks and inspects regions in a separate widget after the timer stops. Initial correctness still matches the same three fixtures, but the paired run stops on the first short-command region comparison: the reference contains a duplicate `none` region that the candidate does not. Exact region parity is the declared gate, so this was retained as a failure rather than normalized away. After the two failed measurement attempts and the independent 154 parser failures, the experiment stopped. A compact-observer performance summary was not produced.

The original verbose-observer timing output and PTY data are retained as rejected diagnostics. The current harness source reproduces the compact-observer comparison and its parity stop; no reproducible speed claim depends on the earlier observer version. Timing measures callback completion, not physical terminal painting. Sanitizer runs are correctness-only.

## Corpus and build identities

The authoritative tests come from the actual pinned upstream syntax-highlighting checkout at `2fc57d63067c18b1100ecdbf684fa5baf49459d1`, with shipped component source overlaid identically in both fixtures. The harness changes only the test driver's fixture-selection loop and runs each case independently, so a parser bailout cannot hide later cases. HOME and ZDOTDIR point to an empty test directory, preventing helper shells from loading the host configuration. All 287 cases run for each owner and each build.

`highlighting-identity.json` records the base revision, compiler, shell and module digests, generated fixtures, SDK header hashes, native source lock and every retained file. The host normal installation is `e70519fc262f3e93a386d74e0ffbe1696a93f44ceb0ec76b19aaf59c7d85c5dc`; archived prototype bytes are additional to base revision `e28e8db`. `highlighting-evidence.tar.gz` contains both complete fixture trees, individual test logs, summaries, editor results and rejected timing diagnostics. The verifier checks the corpus counts, actual failure rows, sanitizer logs, initial editor comparisons and the final parity stop. These are host prototype results, with no installed or glibc-floor adoption claim.

## Reproduction commands

Set `NORMAL`, `SAN`, `SDK` and `OUT` as in the autosuggestion experiment, and `UPSTREAM` to the pinned upstream checkout with its original test corpus. Use fresh output directories when preparing fixtures.

```sh
cc -std=c17 -Wall -Wextra -Werror -O2 -fPIC -shared -I"$SDK/Src" -I"$SDK" native/highlight-parser-prototype.c -o "$OUT/wshhighlightparser.so"
clang -std=c17 -Wall -Wextra -Werror -O1 -g -fPIC -shared -fsanitize=address,undefined -fno-sanitize=function -fno-omit-frame-pointer -I"$SDK/Src" -I"$SDK" native/highlight-parser-prototype.c -o "$OUT/highlight-sanitized/wshhighlightparser.so"
python3 native/prepare-highlight-parser.py "$UPSTREAM" "$OUT" "$OUT/highlight-parser-fixture"
python3 native/prepare-highlight-parser.py "$UPSTREAM" "$OUT/highlight-sanitized" "$OUT/highlight-parser-sanitized-fixture"
taskset -c 1-31 python3 native/test-highlight-parser.py "$NORMAL" "$OUT/highlight-parser-fixture" "$OUT/highlight-corpus-qualified"
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 taskset -c 1-31 python3 native/test-highlight-parser.py "$SAN" "$OUT/highlight-parser-sanitized-fixture" "$OUT/highlight-corpus-qualified-sanitized"
python3 native/test-highlight-parser-zle.py "$NORMAL" "$OUT/highlight-parser-fixture" "$OUT/highlight-parser-compact-zle" correctness
python3 native/test-highlight-parser-zle.py "$NORMAL" "$OUT/highlight-parser-fixture" "$OUT/highlight-parser-compact-zle" measure
```

The last command is expected to stop on region mismatch. The corpus command records failures in `results.json`; its exit status alone is not a correctness gate.
