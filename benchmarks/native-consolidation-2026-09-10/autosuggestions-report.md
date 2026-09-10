# Complete autosuggestion ownership passes the host prototype gates

Moving the controller into C reduced the complete editing sequence from 7.613 ms to 5.552 ms with 10,000 history entries, a 27.1% median improvement. The prototype matched the pinned plugin in ten real editor modes under normal and sanitized builds, and passed pending-child cancellation and oversized-response tests. It remains a private prototype pending installed integration and compatibility qualification.

| History entries | Pinned Zsh controller median | Complete C controller median | Median reduction | Paired p95 candidate minus control | Pairs |
|---|---|---|---|---|---|
| 100 | 6.436 ms | 5.261 ms | 18.3% | -0.470 ms | 50 |
| 10,000 | 7.613 ms | 5.552 ms | 27.1% | -1.646 ms | 50 |

## Ownership and decision

C owns history and previous-command strategy selection, strategy orchestration, completion PTY collection, widget registration, editor actions, suggestion regions, asynchronous reads, stale-result rejection and cancellation. Generated Zsh retains configuration defaults, a small original-widget invocation bridge, completion-engine callbacks and lifecycle hooks. Custom strategies still execute as user Zsh functions. Zsh and ZLE remain the shell and editor.

This is complete controller ownership, not elimination of every Zsh callback. The prototype replaces 867 lines and 27,017 bytes of plugin source with approximately 550 C lines plus 192 generated Zsh lines. Combined source bytes are slightly higher. Its case for further integration is measured editing improvement and a single controller owner, rather than a dramatic reduction in source size.

Keep the shipped pinned plugin selected. The next decision is whether to integrate this controller and qualify installed startup, recognized-copy ownership, modified/active plugin coexistence and the glibc 2.28 build. The private module refuses unloading after widget binding because callbacks would otherwise outlive their owner. That prototype restriction needs an explicit installed lifecycle decision before adoption.

## Correctness and lifecycle findings

The comparison covers synchronous and asynchronous history, vi bindings, custom strategies, asynchronous and synchronous completion, history-ignore patterns, previous-command matching, manual rebinding and disabled job control. It compares actual buffers, Unicode suggestions, partial and full acceptance, replacement, stale responses, disable/re-enable behavior and a custom widget while the existing highlighter is active. All ten control/candidate result rows match in both normal and ASan/UBSan runs.

An adversarial widget name containing spaces and literal shell syntax creates a marker file with the pinned control's wrapping behavior; the C registration path preserves the name without executing it. This intentional difference is recorded separately from editor parity.

The pending-request test uses a real strategy sleeping for 30 seconds, presses Ctrl-C, then requires prompt return, cleared descriptor state and a reaped child within three seconds. A first fix cleared state but did not terminate the child: process substitution inherited the shell's process group, so signalling a group named after the worker did nothing. The worker now establishes its own process group before its PID handshake. The exact final normal build passes, and the sanitized build also passes with job control disabled. A separate sanitized test discards a response larger than the 1 MiB cap and clears its descriptor.

Other prototype corrections kept result delivery inside a ZLE widget, quoted complete widget arguments, and retained the two completion-engine operations that require Zsh's special completion state. These are boundary fixes in the private controller, with no change to the selected plugin.

## Measurement and identities

The fixed [plan](plan.md) requires correctness first, at least 20% improvement for the large-history complete sequence and no more than +1 ms paired p95 regression. Both performance conditions pass. The existing `native/test-autosuggestions-owner.py` harness alternates owner order across 50 paired complete editing and acceptance sequences, pins the editor to CPU 0, uses synchronous history for timing and observes the same PTY markers for both owners. Timing is untraced; sanitizer runs are correctness-only. This comparison does not measure asynchronous completion latency or installed startup.

`autosuggestions-identity.json` identifies the host, compiler, normal and sanitized shell binaries, module hashes, generated fixtures, SDK headers, native source lock and every retained input. The normal shell is development installation `e70519fc262f3e93a386d74e0ffbe1696a93f44ceb0ec76b19aaf59c7d85c5dc`. The base revision is `e28e8db`; archived prototype source records the exact additional bytes tested. `autosuggestions-evidence.tar.gz` contains source snapshots, correctness results, PTY transcripts, paired raw timings and cancellation failures. The evidence verifier recomputes timing statistics and checks the recorded results.

## Reproduction commands

Use the normal installation above as `NORMAL`, the sanitized native installation as `SAN`, and a matching configured Zsh source tree as `SDK`. The retained identity lists their original absolute paths and hashes. These modules are private test artifacts and are not installed by the product build.

```sh
cc -std=c17 -Wall -Wextra -Werror -O2 -fPIC -shared -I"$SDK/Src" -I"$SDK" native/autosuggestions-complete-prototype.c -o "$OUT/wshsuggest.so"
clang -std=c17 -Wall -Wextra -Werror -O1 -g -fPIC -shared -fsanitize=address,undefined -fno-sanitize=function -fno-omit-frame-pointer -I"$SDK/Src" -I"$SDK" native/autosuggestions-complete-prototype.c -o "$OUT/suggestion-sanitized/wshsuggest.so"
python3 native/prepare-autosuggestions-complete.py "$OUT/suggestion-complete-fixture"
python3 native/test-autosuggestions-complete.py "$NORMAL" "$OUT" "$OUT/suggestion-complete-fixture" "$OUT/suggestion-qualified" correctness
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 python3 native/test-autosuggestions-complete.py "$SAN" "$OUT/suggestion-sanitized" "$OUT/suggestion-complete-fixture" "$OUT/suggestion-qualified-sanitized" correctness
python3 native/test-autosuggestions-lifecycle.py "$NORMAL" "$OUT" "$OUT/suggestion-complete-fixture" "$OUT/suggestion-lifecycle-final" correctness
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 python3 native/test-autosuggestions-lifecycle.py "$SAN" "$OUT/suggestion-sanitized" "$OUT/suggestion-complete-fixture" "$OUT/suggestion-lifecycle-sanitized" correctness --no-monitor
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 python3 native/test-autosuggestions-bounds.py "$SAN" "$OUT/suggestion-sanitized" "$OUT/suggestion-complete-fixture" "$OUT/suggestion-bounds" correctness
python3 native/test-autosuggestions-owner.py "$NORMAL" "$OUT" "$OUT/suggestion-complete-fixture" "$OUT/suggestion-final-measure" measure
```
