# Native startup builds from locked repository inputs

The native executable now builds through the repository's verified Zsh builder and reaches a usable prompt without per-user activation state. The comparison against the accepted native workbench passes the 3 ms startup gate with matching runtime and resource bytes. The native distribution owns its defaults, resource paths, and foreground action; Zsh owns user startup files and their execution context.

| Prompt configuration | Alternating pairs | Workbench first-editable median | Locked native first-editable median | Paired p95 increase | Fixed gate |
|---|---:|---:|---:|---:|---:|
| Existing user prompt | 50 | 24.227 ms | 24.621 ms | 0.708 ms | At most 3 ms |
| Minimal Wsh prompt | 50 | 25.091 ms | 25.486 ms | 0.754 ms | At most 3 ms |

The final candidate passes all 75 upstream test scripts with the same two platform skips, 18 native startup cases, five login-style recovery cases, and nine existing Wsh contract suites adapted to invoke the native executable directly. Those suites cover history search, suggestions, highlighting, doctor, directory jumping, named themes, configuration coexistence, real OMZ ownership, and foreground job control. Profiling-specific ownership fixtures await stage 4. Source-digest tampering and reuse of a cached build under different compiler flags are rejected.

## Startup fixes

Native C initializes module and function paths even under `-f`, follows the real executable after relocation or symlink invocation, and leaves user ZDOTDIR changes to Zsh. The payload no longer installs the four redirecting startup files, restoration bookkeeping, repeated shell path setup, or the legacy foreground callback. It currently retains the Rust runtime and a duplicate `bin/zsh` artifact for later migration cleanup.

Two failed counterfactuals are retained. Removing the final setup script initially allowed `.zlogin` to export WSH_THEME into child shells; the native cleanup now removes that export after all user startup. A genuinely empty HOME then reached the upstream first-run wizard through a configured build-prefix script. Successful Wsh integration now suppresses automatic `zsh/newuser` loading, so a fresh account reaches a prompt without creating configuration. Missing integration retains upstream startup behavior. Missing, unreadable, or incompatible optional runtimes also leave the shell usable.

## Measurement and identities

The [plan](plan.md) fixed correctness, 50 alternating pairs per prompt, a 3 ms paired p95 limit, and attempt/time bounds before implementation. Timing uses trace-off PTYs pinned to CPU 0, an isolated HOME, matching global-startup policy, and the primary native OSC 133 editable marker. The control is a copy of the accepted foreground workbench with its runtime, modules, and Zsh function resources replaced by the candidate bytes. Its old binary and three startup adapters remain. This prevents Cargo dependency or resource changes from being attributed to native startup. Configured build prefixes differ and are retained in the build logs.

The unsigned candidate is bundle `1dec372bc0af0158ff0a2f95587ff01f91fb4c71d3dc1de3d866c7c95a2630dc`, built from `4dafee9cb740677a50f8fe22677235089c7b311d+dirty` and native lock `8cd879059d723dedfb7ef0bb8196af388ca904c5f9208e9a17e094031e6cb605`. [build.json](build.json) records compiler, binary, matched resources, source inputs, commands, and sanitizer identity. The manifest and source archive retain the exact accepted inputs; the results archive retains tests, converted fixtures, failures, all four build logs, and sanitizer logs. The earlier builds are diagnostic attempts, not accepted artifacts.

ASan/UBSan passes the same 18 startup and five recovery cases on the final C implementation. The established whole-Zsh sanitizer configuration excludes Clang's function-type check because of the independently reproduced upstream hashtable callback cast, and disables leak checking for Zsh's process-lifetime allocations. This does not establish package, PAM, GDM, SELinux, reboot, upgrade, or glibc-floor qualification; those belong to the following stages.

Reproduce the build with `./build/build-native-installation.zsh`, then run `native/test-startup.py`, `native/test-recovery.py`, and `native/check-installation.py` against its printed bundle path and separate output directories. The exact measured command is retained in [metadata.json](metadata.json). Verify retained evidence with `python3 benchmarks/verify-native-build-evidence.py`.
