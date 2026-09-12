# Jansson reduces helper size and memory with similar prompt latency

Using the existing system Jansson library reduced the helper executable from 372,320 to 114,912 bytes, about 69%, and reduced median shell-plus-helper PSS by 258.5 KiB. Startup and Git-refresh comparisons passed every fixed latency gate. I compared two helpers built from the same current C sources, changing only JSON handling, then ran both with byte-identical native shell executables.

I recommend consolidating on Jansson after explicitly choosing the protocol's integer bounds. This prototype leaves production sources and dependencies unchanged. It does not promise a prompt speedup: the isolated ping comparison became about 1.8 microseconds slower.

## Correctness and protocol differences

Both normal and ASan/UBSan candidate runs compared 2,237 independent decoder cases against the yyjson helper, including 2,000 deterministic malformed-frame mutations. Exactly seven responses differed:

- Six requests containing `18446744073709551615` in an ID, generation or duration were accepted by yyjson and rejected by Jansson. Jansson rejects out-of-range integers during decoding.
- A request ID spelled `-0` was rejected by yyjson and accepted as zero by Jansson.

The remaining 2,230 decoder cases matched. Another 400 complete prompt and snapshot comparisons passed across Minimal, Wakamex, Robbyrussell and Agnoster, with IDs and durations through INT64_MAX, signed exit-status boundaries, transient resets and privileged state. Each decoder case used fresh helpers to prevent divergent state in one case from contaminating later comparisons.

The existing 15-case helper lifecycle suite passed for the control, normal candidate and sanitized candidate: cancellation, worker cleanup, partial messages, EOF, input bounds, signal shutdown, live tracing and buffered profiling. The installed candidate also passed all four named-theme tests and native profiling attribution, recovery, privacy, argument and exit-status checks.

The shell declares IDs and generations as Zsh integers and computes command duration in a local integer, so its ordinary requests fit the signed range. A real switch should document the nonnegative INT64 range, update the full-range protocol tests and decide that JSON `-0` means zero. The prototype adds no custom integer decoder or compatibility layer to retain the old boundary behavior.

## Latency results

Values are milliseconds except the explicitly labeled ping row. The paired p95 column is candidate minus control, calculated within each alternating pair. All startup and refresh gates were fixed at a maximum 3 ms paired p95 increase before implementation.

| Workload | yyjson median | Jansson median | Paired p95 increase | Gate |
| --- | ---: | ---: | ---: | --- |
| Existing prompt, first editable | 20.033 ms | 20.047 ms | 0.554 ms | Pass |
| Minimal prompt, first editable | 22.198 ms | 22.175 ms | 0.360 ms | Pass |
| Clean Git repository, fresh helper after ready | 8.955 ms | 8.877 ms | 0.233 ms | Pass |
| Clean Git repository, warm helper | 8.628 ms | 8.685 ms | 0.295 ms | Pass |
| Dirty Git repository, fresh helper after ready | 3.969 ms | 3.972 ms | 0.156 ms | Pass |
| Dirty Git repository, warm helper | 3.814 ms | 3.844 ms | 0.132 ms | Pass |
| Untracked files, fresh helper after ready | 4.203 ms | 4.251 ms | 0.215 ms | Pass |
| Untracked files, warm helper | 4.079 ms | 4.114 ms | 0.180 ms | Pass |
| JSON ping round trip, no Git or editor work | 10.95 us | 12.73 us | 3.46 us | Diagnostic |

Startup used the actual OSC 133 editable marker and 50 alternating pairs per prompt mode. Git collection used 50 alternating pairs for each repository state and process mode, with 1,000 tracked files and 100 changed or untracked files where applicable; every compared snapshot matched. Filesystem caches were not forcibly evicted. Ping used 1,000 alternating pairs after 50 warmup pairs. All timing runs used CPU 0 and tracing disabled; trace behavior was checked separately in correctness tests.

## Memory and executable size

| Measurement | yyjson | Jansson | Difference |
| --- | ---: | ---: | ---: |
| Helper executable file | 372,320 bytes | 114,912 bytes | -257,408 bytes (-69.1%) |
| Median shell-plus-helper PSS | 3,676 KiB | 3,417.5 KiB | -258.5 KiB |
| Largest paired shell-plus-helper PSS change | | | -192 KiB |

Memory used 20 alternating pairs, sampled 100 ms after the first editable marker. Every shell had exactly one helper. The fixed maximum increase gate was 4 MiB; all pairs used less memory with Jansson. PSS includes mapped shared-library pages proportionally, while executable file size excludes the shared Jansson library. Jansson 2.14 was already a system dependency of the unchanged shell.

## Reproduction and retained inputs

The [plan](plan.md) fixes the hypothesis and gates. The [candidate patch](candidate.patch) changes four helper files, using Jansson directly and retaining the existing Git, renderer and theme parser code. The [identity record](identity.json) records source, shell and helper digests, manifests, compiler identities, parser/library hashes, source inputs and the exact measured build commands. [Raw evidence](evidence.tar.gz) contains decoder responses, lifecycle results, traces, samples, summaries, build logs and both installation manifests. [Summary data](summary.json) preserves unrounded results.

The source baseline is `8563422ea41cf595a47ac8169df8219787b973dc`. The shell is the previously tested unsigned native installation identified in `identity.json`; only its helper was replaced in each isolated copy. Host helper builds used GCC 16.2.1 and `-O2`, with the same native/theme sources. Sanitizer builds used Clang 22.1.8 because the host GCC sanitizer libraries were missing. Jansson itself was the ordinary system shared library.

With the native build dependencies, system Jansson development headers and Clang sanitizer runtime installed, reproduce from this source and experiment:

```sh
zsh -df benchmarks/jansson-2026-09-12/reproduce.zsh EXISTING_NATIVE_INSTALLATION NEW_OUTPUT
python3 benchmarks/jansson-2026-09-12/verify.py
```

The reproducer accepts normal `CC`, `CFLAGS`, `CPPFLAGS`, `LDFLAGS` and `WSH_SANITIZER_CC` overrides. On this host, the measured candidate used the local development-header SDK paths recorded in the identity file and linked the system `libjansson.so.4`.

This is a host prototype comparison. System-package and glibc-floor qualification remain necessary before selecting it for a release.
