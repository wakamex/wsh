# Native tool results

Compiled version reporting works without user state or installed resources. Native argument checks and 10,000 arbitrary-byte sanitizer cases pass. Fifty alternating process-exit measurements gave a -0.116 ms paired p95 difference against upstream version output, passing the predeclared +3 ms regression gate.

The accepted version slice adds 38 lines of tool C plus an explicit first-argument dispatch. It needs no new runtime library, metadata parser, helper process, or activation record. It reports compiled source and input identities and explicitly states that installed resources are unverified. The standalone manager remains in production until its other consumers migrate.

The checks cover ordinary scripts named doctor, profile, version, update and run; native `-c`, `-s`, `-f` and `--`; exit statuses and non-UTF-8 argument bytes; poisoned startup; absent HOME; corrupt activation data; a relocated executable with non-UTF-8 path bytes; and mismatched adjacent metadata. Missing metadata cannot alter compiled identity. Strict compiler diagnostics, ASan, UBSan and leak detection passed the dispatcher harness. Full native-shell sanitizers and installed-resource validation belong to subsequent stages.

The first build failed because Zsh's prototype generator copied an include placed after a declaration marker into generated headers. Moving it before the marker resolved that build integration error. The failed build log is retained. The normal build also emitted the existing documentation formatter fallback messages; compilation and the command tests passed.

`build.json` identifies the source, complete native input digests, generated definitions, compiler, configure arguments and two binaries. `version-inputs.tar.gz` preserves the tested code independently of subsequent work. `version-samples.json` retains all 50 pairs, including alternating order by pair parity. `version-summary.json` records the nearest-rank statistic, fixture environment, CPU and exact sanitizer command. Timing uses one pinned CPU, no tracing, five warmup pairs, and subprocess exit including captured output. It does not measure editor readiness.

Doctor is the next independent slice. The workbench is local and unsigned; production startup and package adoption have not changed.
