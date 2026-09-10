# Native autosuggestions selected after installed qualification

The installed C controller preserves the tested editor and plugin-ownership behavior and improves the complete large-history editing sequence by 29.3%. First-editable startup improves by approximately 6.6 ms in both tested prompt modes. Normal and sanitized editor comparisons, real OMZ coexistence and the canonical glibc 2.28 build pass. Native installations now select this controller.

| Installed workload | Pinned plugin control | Native controller | Comparison | Gate |
|---|---|---|---|---|
| Complete editing sequence, 100 history entries | 5.623 ms median | 4.410 ms median | 21.6% faster; paired p95 delta -0.953 ms | At most +1 ms paired p95 regression |
| Complete editing sequence, 10,000 history entries | 7.294 ms median | 5.160 ms median | 29.3% faster; paired p95 delta -1.801 ms | At least 20% median improvement and at most +1 ms paired p95 regression |
| First editable prompt, existing presentation | 22.558 ms reported median | 15.989 ms reported median | Paired p95 delta -6.159 ms | At most +3 ms regression |
| First editable prompt, minimal presentation | 24.572 ms reported median | 17.946 ms reported median | Paired p95 delta -6.194 ms | At most +3 ms regression |

## Integration and compatibility

`native/autosuggestions.c` is the qualified controller compiled directly into the shell. It owns strategies, widget registration and actions, completion collection, suggestion regions and asynchronous lifecycle. `native/prepare-autosuggestions.py` generates the small configuration and ZLE/completion adapter from the pinned upstream snapshot. The previous private module source remains an immutable experimental reference. Shell-lifetime builtins remove its dynamic-module unload restriction.

The existing compatibility adapter still recognizes exact source bytes before replacing an inactive external copy. Active, modified and unknown implementations remain external; disabling the default preserves that choice. The pinned source and license remain packaged for recognition and provenance. Manual and automatic rebinding retain their public settings, and the generated adapter supplies `_zsh_autosuggest_bind_widgets` for late widget registration. The source-path assertion and exact hook-list assertions in the existing contracts now describe the native adapter and its cleanup hooks.

The normal installed comparison matches the pinned control in ten modes: synchronous/asynchronous history, vi, custom strategies, synchronous/asynchronous completion, history-ignore, previous-command matching, manual rebinding and disabled job control. The same ten comparisons pass in the sanitized fixture. Pending cancellation and oversized-response tests pass in both; the sanitized cancellation case disables job control. These tests run through the installed startup adapter, with no private test module loaded.

All nine existing installed compatibility suites pass, including history/highlighting composition, plugin doctor, configuration coexistence, foreground jobs and prompt ownership. Five real OMZ configurations cover exact pending replacement, active preservation, modified preservation, disabled defaults and automatic rebinding. They preserve compdef, verify doctor advice, and check that a later public widget is wrapped after explicit manual rebinding or the next automatic prompt transition.

The canonical Rocky Linux 8.10/glibc 2.28 run passes the upstream Zsh suite, all nine contracts, the new installed autosuggestion tests, recovery, profiling, completion, history, directory and runtime checks, plus RPM inventory agreement. The new autosuggestion regression commands are part of `build/test-native-installation.zsh`.

## Measurement and retained identities

The [fixed plan](plan.md) precedes integration. Editing uses 50 alternating pairs per history size through the same existing PTY harness, with synchronous history and matching accepted buffers. Startup uses 50 alternating pairs per prompt mode and the native OSC 133 editable marker. It reports the existing harness's lower-middle median and paired p95; passing this stricter percentile also passes the planned p90 threshold. The editor is pinned to CPU 0. Concurrent floor compilation was moved to CPUs 1-31 before timing, and sanitizer/editor correctness runs finished first. Neither timing run enables tracing or sanitizers.

`identity.json` records source revision `3fcad96` plus the exact integration source snapshot, compiler/build metadata, normal and sanitized binary hashes, baseline and candidate manifests, floor command and every retained file. The installed normal candidate is `f318bec1a15d5a67ecfa51e640527c235ba89f0b9ae3c8ffadfdadab50e04afb`. The startup control is the previous native installation `e70519fc262f3e93a386d74e0ffbe1696a93f44ceb0ec76b19aaf59c7d85c5dc`. Both remain unsigned development artifacts. `evidence.tar.gz` retains source, generated fixtures, raw paired measurements, transcripts, logs and counterfactual failures. The verifier recomputes the accepted gates.

## Sanitizer scope and independent failures

ASan/UBSan component qualification uses a private installed-layout fixture with the current C sources rebuilt into the existing sanitized Zsh SDK and the current generated adapter. Its ordinary helper is unchanged. It is explicitly marked as a test fixture, not a distributable installation; leak detection is disabled and undefined-behavior failures stop execution. All autosuggestion comparisons and lifecycle/bounds checks pass without sanitizer diagnostics.

A fresh full sanitized build ran 72 upstream scripts successfully, with failures in K01nameref, V07pcre and Y06values and two skips. Each failing script also fails against the previous sanitized shell using the same test driver. These failures are retained and are not counted as a successful full sanitized upstream suite. Normal host and canonical floor upstream suites pass. Initial host setup also exposed missing Jansson development flags, and a namespace conversion accidentally renamed the BUILTIN macro; both build-only errors were corrected before runtime qualification. The first compatibility run used a container-built test driver outside its compiled module path; the corrected run uses the host-pinned driver.

The OMZ experiment independently reproduced a diagnostic timeout under a controlling terminal. Both the previous native shell and this candidate time out after ten seconds; the diagnostic child's separate process group encounters terminal job control. Doctor ownership/advice checks pass in a detached diagnostic session. This pre-existing terminal-doctor failure is separate follow-up work and was not changed by autosuggestion adoption. Its paired reproducer and transcripts are retained.

## Reproduction

The normal host build uses `CPPFLAGS=-I/var/tmp/wsh-native-sdk/usr/include` and `LDFLAGS=-L/var/tmp/wsh-native-sdk/usr/lib64` for this host's extracted Jansson headers/library. Run `build/build-native-installation.zsh` with a fresh `WSH_ZSH_OUTPUT_ROOT`. The floor command and its exact SDK identity are retained in `floor-command.json`.

```sh
python3 native/test-installed-autosuggestions.py INSTALLATION OUTPUT correctness
python3 native/test-installed-autosuggestions.py INSTALLATION OUTPUT_LIFECYCLE lifecycle
python3 native/test-installed-autosuggestions.py INSTALLATION OUTPUT_BOUNDS bounds
python3 native/test-autosuggestions-omz.py INSTALLATION OMZ_CHECKOUT OUTPUT_OMZ
python3 native/check-installation.py INSTALLATION OUTPUT_CONTRACTS
python3 native/test-installed-autosuggestions.py INSTALLATION OUTPUT_MEASURE measure
python3 native/measure-startup.py PREVIOUS_INSTALLATION INSTALLATION OUTPUT_STARTUP
```

For contracts, set `WSH_TEST_ZSH` and `WSH_REFERENCE_ZSH` to the host-pinned reference, and `WSH_TEST_OMZ` to the real checkout. Repeat component correctness/lifecycle/bounds with the sanitized fixture and `ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1`; add `--no-monitor` to its lifecycle command. The archived build logs, configured SDK input hashes and binary hashes identify that incremental sanitizer build separately from the normal installation.
