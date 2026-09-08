# Native doctor results

Native doctor passes plugin and prompt compatibility, failure-state, cleanup and sanitizer checks. Its final matched comparison is 1.884 ms faster at paired p95 than the Rust command, passing the +3 ms gate across 50 alternating pairs. It uses the normal native startup path and reads ownership directly in C.

The native implementation has 212 lines of doctor C, plus dispatcher and initialization calls, compared with 242 lines of Rust production doctor code including its embedded shell report command. It removes the temporary report file, report schema/parser, reconstructed shell reporting command and additional exec boundary. Both implementations still isolate configuration in a child. No new library or runtime dependency is added. The Rust manager remains available for consumers that have not migrated.

## Compatibility and cleanup

The same installation produced identical Rust and C output for clean configuration, three exact plugin copies, three modified copies, disabled components, the recognized OMZ history copy, an active autosuggestion copy, noisy startup, real OMZ prompt overlap, and the user's conditional theme opt-out pattern. The real OMZ checkout was 605a393f1c4734b23c6551370b9d542724e77879. Startup files were checked unchanged.

Early successful and failed startup exits fail the diagnostic instead of pretending to return ownership. A hung startup reaches the ten-second bound; SIGTERM returns 143 promptly. Fifty repeated reports passed. Additional cases cover missing/corrupt/unreadable activation state, rejected extra and non-UTF-8 arguments, inconsistent/oversized/control-containing ownership, absent installed integration, and background-job cleanup. A private mount namespace with a real `/etc/zshrc` fixture proves native doctor reads global startup; binding an empty file makes the same startup assertion fail.

The first implementation used `_exit` after reporting and failed the background-job check. Routing completion through Zsh's own `zexit` fixes that observed leak and preserves native exit handling. Process-group cleanup bounds the diagnostic child on timeout/interruption. This does not claim control over deliberately detached services launched by user configuration.

## Matched measurement and failed hypotheses

The first comparison failed at +55.335 ms paired p95 because native doctor read Fedora global startup while Rust forced `-d`. A syscall trace identified `/etc/zshrc` and `/etc/profile.d` programs. The matched fixture now uses `unsetopt globalrcs` in its `.zshenv` for both variants. Native product behavior continues to include global startup. The threshold and sample count were unchanged.

That matched run still failed at +7.044 ms. The parent observed report EOF before the child became waitable and entered its ten-millisecond final polling wait. Keeping the descriptor open until process exit also failed at +6.986 ms. Reducing only the post-EOF wait to one millisecond passed at -2.103 ms. After the separate native-exit cleanup fix, the final comparison passed at -1.884 ms. The report wait itself remains event-driven and all paths retain the ten-second bound.

All four preceding runs, source input digests, raw samples and premise audits are retained. Failed-run input archives are reconstructed from unchanged current files and the recorded doctor source; every reconstructed byte is checked against the original build digest. Final timing uses one CPU, no tracing, 50 alternating pairs, the same empty user configuration and global-file policy, and complete process exit including captured output. The Rust control verifies the same installation manifest before diagnostic startup, as its production command does.

## Sanitizer coverage

The exact ownership classifier passed 40 declared combinations and 10,000 arbitrary byte-string pairs under ASan and UBSan with `-Wall -Wextra -Werror`. The dispatcher sanitizer harness also passed again. The full Zsh core was compiled with Clang, ASan and UBSan; all eight diagnostic boundary checks passed against that binary. Installed dynamic modules remain the baseline release modules.

The initial sanitized build exposed the host's missing GCC ASan runtime because Zsh's module linker remained GCC; explicitly selecting Clang for both compiler and module linker fixed the build. Full-shell UBSan then reported an existing incompatible hashtable callback type in unchanged `params.c`, also reproduced with `-f -c 'typeset -A a; a[x]=y'`. The full-shell run excludes the function-pointer check and leak detection; other ASan/UBSan checks remain enabled. The standalone classifier and dispatcher have neither exclusion. These limits and the upstream reproducer are retained in separate records.

## Identity and reproduction

`build.json`, `inputs.tar.gz`, the compressed installation manifest, sanitized build record, original build logs, fixture outputs, raw samples and summaries identify the tested source and binaries. Reproduce the retained startup prototype first, then run the archived `native/build-tools.py`, `native/test-doctor-boundaries.py`, `native/test-doctor.py`, `native/test-tools.py` and `native/test-ownership.py`. These builds remain local unsigned development artifacts.

All 75 upstream Zsh test scripts also pass, with the same two skips.

Stage 1 is accepted for integration into the native path. Production startup and installed command migration are handled by the following stages.
