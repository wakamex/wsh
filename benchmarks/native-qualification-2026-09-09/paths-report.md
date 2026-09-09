# Native relocation removes stale build-directory fallbacks

Native Wsh now replaces its compiled module/function defaults with installation-relative paths. A relocated shell no longer silently loads a missing function from the original build tree. An explicitly exported `FPATH` retains the user's paths, and the fixed system site-function directory remains available. The change passes resource-ownership checks, 18 native startup cases in ordinary and sanitized builds, and all nine component contracts with both Rust and C helpers, including real OMZ coexistence.

| Prompt ownership | Control readiness median | Corrected readiness median | Paired p95 change | Limit |
|---|---:|---:|---:|---:|
| Existing prompt | 24.778 ms | 24.580 ms | +0.755 ms | +3 ms |
| Minimal Wsh prompt | 25.517 ms | 25.475 ms | +0.433 ms | +3 ms |

## Accepted correction

Previously, native setup prepended relocated paths but left the build-prefix function, site-function and module paths as fallbacks. The baseline output records those exact entries. This both duplicated completion scanning while the build tree existed and allowed fallback into another installation's resources. The correction removes the exact compiled module/function defaults and relocates the compiled site-function default. It preserves unrelated paths. The explicit environment `FPATH` case remains user-owned, including deliberately named build directories.

The test copies a real native installation, loads a relocated module and autoloaded function, verifies explicit custom function paths, then removes the relocated function and requires lookup to fail despite the original compiled tree remaining available. Native startup, foreground job control, prompt ownership, profile invocation and existing plugin contracts still pass. No user files or installed account shell were changed.

## Method and build failures

The source baseline is `20da944`. Both performance variants use the same tested C helper bytes; the changed boundary is native resource setup. Each prompt mode has 50 alternating matched readiness pairs on CPU 0, observed through native primary-prompt and editor-ready OSC markers. All samples are retained. The source lock, exact native sources, build identities, original path output, contract logs and measurement inputs are archived.

The first sanitizer rebuild used configured `make` defaults instead of the previous command-line overrides. A subsequent attempt omitted the configured capability library, and the next exposed the separately configured GCC module linker. The final rebuild restores the configured library list and explicitly uses Clang for both compilation and module linking. These build-layer failures are retained; no runtime failure was attributed to the resource correction. The final core contains AddressSanitizer and UndefinedBehaviorSanitizer instrumentation and passes the 18 startup cases and focused relocation checks with the previously documented upstream leak/function-sanitizer exceptions. Ordinary upstream shell tests also pass in the final locked native build.

This fixes current relocation ownership. Cross-ABI resources for an already running shell during a future package replacement remain a separate qualification boundary.
