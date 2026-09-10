# Installed native completion passes its fixed gates

The bundled native scanner reduces cold completion startup p95 from 155.43 ms to 123.60 ms while preserving real compinit registration, security checks, cache policy and editor behavior. Its 99.04 ms overhead over minimal startup passes the fixed 100 ms gate with a narrow 0.96 ms margin. Fifty alternating samples per variant cover cold, warm, stale and unusable caches plus first and second Tab. Both normal and ASan/UBSan installed correctness runs pass.

| Cache state | Original startup p95, ms | Native startup p95, ms | Native overhead over minimal startup, ms | Fixed overhead limit, ms | Native first Tab p95, ms | Native second Tab p95, ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Cold | 155.429 | 123.600 | 99.041 | 100 | 71.166 | 25.139 |
| Warm | 37.608 | 37.775 | 13.217 | 20 | 71.397 | 25.033 |
| Stale | 153.838 | 123.355 | 98.796 | 100 | 71.704 | 24.995 |
| Unusable | 154.102 | 122.664 | 98.105 | 100 | 70.996 | 24.865 |

Minimal startup p95 is 24.559 ms. Both Tab budgets remain 100 ms. These are installed, unsigned host development artifacts, not a published release or a fresh glibc-floor qualification.

## Integration and memory lifetime

The native build registers `wsh-completion-scan` in the shell. Its bundled compinit invokes the scanner only in the cold registration branch and uses the unchanged upstream loop when that builtin is absent, including under regular Zsh. User-supplied compinit functions are not rewritten. Compaudit, compdump, completion functions and widget behavior retain their existing owners.

A targeted DEBUG trap replacing `_i_line` during the autoload callback reproduced an ASan heap-use-after-free in the initial scanner. The first fix copied every header array. That version passed correctness but missed cold, stale and unusable overhead gates by 1.0–1.5 ms. The accepted fix constructs autoload metadata before entering the shell callback, so the scanner never reads borrowed header fields afterward. This removes the unconditional copy. Both the failure and passing rerun are retained; thresholds were unchanged.

## Retained evidence and reproduction

`identity.json` binds the final source inputs, compiler, host, unsigned bundle and normal/sanitized binary digests. The selected source lock records upstream Zsh, patch and native input identities; `joined-manifest.json` records the installed payload. `inputs.tar.gz` retains measured sources and harness dependencies; `results.tar.gz` retains both 450-shell timing experiments, correctness cases, generated configuration, completion dumps and PTY transcripts. Build logs retain the upstream suite, and the earlier complete installed contract run is retained separately. The final scan change was checked with the installed completion suite rather than repeating unrelated contracts.

Build with `CPPFLAGS=-I/var/tmp/wsh-native-sdk/usr/include LDFLAGS=-L/var/tmp/wsh-native-sdk/usr/lib64 WSH_ZSH_OUTPUT_ROOT=/var/tmp/wsh-native-adoption/build-joined ./build/build-native-installation.zsh`. Run `python3 native/test-installed-completion.py BUNDLE REFERENCE OUTPUT correctness`, then the same command with `measure`; the reference is unsigned installation `4bfc1bd9af7cf33c315f62a65db66eceb64a9ffba4585144b7ee2732106f0986`. The harness pins timing shells to CPU 0, runs 50 alternating samples per variant with tracing off, and compares the installed patched compinit against the reference's pinned original function. Correctness precedes timing.

The sanitized fixture uses Clang with `-O1 -g -fsanitize=address,undefined -fno-sanitize=function -fno-omit-frame-pointer`, `ASAN_OPTIONS=detect_leaks=0` and `UBSAN_OPTIONS=halt_on_error=1`. Its shell executables replace those in a private copy of the installed payload; the copied manifest is not an identity claim for that instrumented fixture. Run the same correctness command against it. `benchmarks/verify-native-completion-adoption.py` recalculates every retained timing gate and checks the input and lifetime-regression evidence.
