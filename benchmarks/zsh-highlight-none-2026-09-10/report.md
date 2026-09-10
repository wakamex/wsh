# Neutral highlight regions retain ownership and layer metadata

The bundled Zsh now consumes its own `none` highlight representation, preserving following ownership and layer fields. This lets syntax-highlighting remove its neutral regions on later redraws instead of retaining stale entries. Five real-ZLE round trips pass in normal and sanitized builds, and identical highlighters now produce identical composed regions across 50 paired redraws in each of four workloads.

## Reproducer and cause

At Zsh revision `cad0d67c76e2be7371cf3526b79ea2581810d35a`, setting `region_highlight=('0 1 none memo=probe')` returns `0 1 none`. A colored region retains its memo. `none,layer=4 memo=probe` loses both the layer and memo. The failure is in the native attribute parser: `output_highlight()` emits `none` for an empty mask, but `match_highlight()` does not consume it. The region setter cannot reach the following fields.

The pinned syntax-highlighting plugin tags its regions with `memo=zsh-syntax-highlighting` and removes those regions before repainting. Losing the tag means neutral regions survive cleanup. In the editor experiment, additional redraws left duplicate regions, and later text insertion shifted them outside the current buffer. Two identical upstream highlighters therefore produced different lists depending on redraw scheduling. The earlier highlighting experiment's region mismatch was not evidence of a candidate-parser defect; the independent 154 upstream parser failures remain valid.

The narrow source patch recognizes only a delimited `none` token, preserving its no-attribute meaning and continuing attribute parsing. It does not change the highlighter's vendored source or introduce another region owner. The [upstream candidate record](../../UPSTREAM-ZSH-BUGS.md#neutral-highlight-attributes-discard-ownership-metadata) includes a minimal interactive widget and submission status.

## Verification

The regression uses the real ZLE setter/getter, with other Wsh editor defaults disabled for isolation. It checks a colored control, neutral style, comma-separated neutral style, explicit layer and a combination of bold plus neutral style. Exact canonical representations and a second assignment must preserve metadata. The original shell loses metadata in four of five cases; patched normal and ASan/UBSan shells pass all five.

The host upstream Zsh suite and all nine installed Wsh contracts pass. The patched highlighter retains all 287 original upstream fixtures in normal and sanitized runs, and composed editor checks retain exact ordered regions with the installed native autosuggestion owner. A 50-pair identical-control run passes on short, repeated-command, distinct-command and multiline buffers. The canonical glibc 2.28 build also runs the round-trip regression, upstream Zsh suite, complete installed contracts and RPM validation. This regression is now part of the normal canonical build.

Sanitizer qualification uses the existing configured sanitized SDK rebuilt with the patched prompt parser and current native source identities. It is a private installed-layout fixture, with ASan/UBSan enabled, function sanitizer and leak detection disabled. It does not imply that the separately documented full sanitized upstream suite is green.

## Evidence and commands

`identity.json` records source and binary hashes, the original and patched prompt parser, source locks, compiler/configuration inputs, installation manifests and every archived result. `evidence.tar.gz` retains minimal reproductions, before/after editor observations, the traced failure, source snapshots, host/floor logs and normal/sanitized results. The normal patched installation is `70f4b5721d0b2676ef94830d75707d22a0f69d6bda82da4c953696eb16d5bd8e`; the original control is `f318bec1a15d5a67ecfa51e640527c235ba89f0b9ae3c8ffadfdadab50e04afb`. Both are unsigned development artifacts, based on `c78fbf4` plus retained local changes.

```sh
python3 native/test-highlight-roundtrip.py ORIGINAL/bin/wsh OUTPUT_BEFORE --expect-failure
python3 native/test-highlight-roundtrip.py PATCHED/bin/wsh OUTPUT_AFTER
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 python3 native/test-highlight-roundtrip.py SANITIZED/bin/wsh OUTPUT_SANITIZED
python3 native/test-highlight-traversal-zle.py PATCHED/bin/wsh IDENTICAL_FIXTURES OUTPUT_OBSERVER correctness
python3 native/test-highlight-traversal-zle.py PATCHED/bin/wsh IDENTICAL_FIXTURES OUTPUT_OBSERVER measure
```

The identical fixtures contain two copies of the pinned original highlighter. The observer snapshots regions at the end of the composed redraw hooks, sends a compact marker and serializes the snapshot after timing. Moving the observation point alone did not fix the original failure; the native parser patch did. The repeated redraws establish exact region parity; no speed claim is needed to accept this correctness fix.
