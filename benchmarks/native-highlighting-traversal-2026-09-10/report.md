# Native traversal preserves highlighting but misses the performance gate

The C traversal candidate passes all 287 upstream fixtures in both normal and sanitized runs, including exact composed editor regions after fixing Zsh's neutral-highlight metadata bug. It improves complete redraw medians by only 0.9–2.6%, below the fixed 20% gate. Keep it private and retain the existing parser. The accepted product change from this investigation is the [Zsh ownership-metadata fix](../zsh-highlight-none-2026-09-10/report.md).

| Complete redraw workload | Original parser median | C traversal median | Median reduction | Paired p95 candidate minus control | Decision |
|---|---|---|---|---|---|
| Short command | 1.983 ms | 1.963 ms | 1.0% | +0.825 ms | Improvement gate fails |
| 100 repeated commands | 120.372 ms | 118.286 ms | 1.7% | +3.205 ms | Improvement and regression gates fail |
| 100 distinct defined commands | 129.225 ms | 125.862 ms | 2.6% | +3.969 ms | Improvement and regression gates fail |
| Multiline conditional with expansion | 5.186 ms | 5.142 ms | 0.9% | +0.528 ms | Improvement gate fails |

## Boundary and interpretation

The previous approximate parser passed 133/287 fixtures because it replaced the upstream grammar with a simplified state machine. This experiment preserves that state machine and ports only the repeated whitespace scan, character-position accounting, newline restoration and remaining-buffer slicing. Recursion, aliases, parameter expansion, stacks, command classification and style ordering remain upstream-owned. It is a faithful narrow boundary, not complete C parser ownership.

All 287 fixtures pass before and after the independent Zsh fix, with identical normal/sanitized results. All four composed editor workloads match after the fix. That establishes a compatible traversal boundary, but its small measured effect does not justify installing a new native interface. A larger port would need to preserve the actual upstream state transitions and their source positions. Reintroducing the earlier simplified grammar would repeat a disproved premise.

The large-workload identical-control run itself had paired p95 differences of 6.780 ms and 8.156 ms. This environment cannot resolve small tail differences at the +1 ms gate on those workloads. No threshold was relaxed and no timing samples were removed. The median improvements are also far below 20%, so the result does not justify another timing attempt or adoption.

## Observer correction and overhead

The original observer failed on the second short redraw even when both sides used identical source. Capturing the regions earlier did not cure that failure. Tracing showed neutral regions surviving cleanup after Zsh discarded their memo. The local native fix restores deterministic exact region comparisons; it does not normalize away differences.

Both timed owners use the same callback-boundary capture and compact marker, followed by diagnostic serialization outside the timed interval. A separate 50-pair identical-source experiment moves the array capture outside the timed callback on one side. Median capture differences are +0.079 ms for short input, +0.579 ms for repeated commands, +0.469 ms for distinct commands and -0.091 ms for multiline input. The negative observation and large-workload tail variability are measurement noise, not evidence of negative overhead. No overhead subtraction is applied to the candidate comparison. Timing ends at callback completion, not physical terminal painting.

## Method and retained inputs

The [plan](plan.md) records the baseline, narrow counterfactual, fixed gates, two-intervention audit and two-hour bound. Correctness precedes timing. Each workload has 50 pairs with alternating owner order, exact ordered region comparison and CPU 0 affinity. Tracing and sanitizers are disabled during timing. Concurrent corpus checks and floor compilation use other CPUs. The corpus uses the pinned authoritative upstream tests one case at a time, preventing a bailout from hiding later cases.

`identity.json` identifies the current native-autosuggestion shell, patched shell, sanitized shell, module bytes, matching SDK headers, source revision and every archive input. `evidence.tar.gz` retains generated fixtures, complete corpus logs, paired samples, editor transcripts and the observer-overhead comparison. Original failed observer evidence is retained with the separate Zsh fix. The BSD notice is retained in the C prototype, and vendored bytes remain unchanged. No parser or traversal prototype enters the installed payload.

```sh
cc -std=c17 -Wall -Wextra -Werror -O2 -fPIC -shared -I"$SDK/Src" -I"$SDK" native/highlight-traversal-prototype.c -o "$OUT/wshhighlighttraversal.so"
python3 native/prepare-highlight-traversal.py UPSTREAM_CHECKOUT "$OUT" FIXTURE
python3 native/test-highlight-parser.py PATCHED/bin/wsh FIXTURE CORPUS_OUTPUT
python3 native/test-highlight-traversal-zle.py PATCHED/bin/wsh FIXTURE EDITOR_OUTPUT correctness
python3 native/test-highlight-traversal-zle.py PATCHED/bin/wsh FIXTURE EDITOR_OUTPUT measure
```

Repeat the corpus and editor correctness with the sanitized module and shell, using ASan/UBSan flags recorded in the identity. For observer overhead, use two identical original fixtures and add `--capture-overhead` to both correctness and measure commands.
