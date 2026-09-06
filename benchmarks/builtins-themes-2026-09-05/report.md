# Built-in directory jumping and two named theme ports

Wsh now supplies directory jumping when no existing z command is configured, and accepts WSH_THEME=robbyrussell and WSH_THEME=agnoster. Existing OMZ directory jumping remains its sole owner. The complete host suite, real OMZ coexistence tests, native ZLE completion tests, and all four theme launch checks passed. The accepted 100-pair comparison measured 2.810 ms p90 extra startup for directory jumping, passing the fixed 3 ms gate.

The tests exercised the pinned implementation through real bundled Zsh, checked persistent ranked jumps and paths with spaces, and verified named themes through the launcher and trusted renderer. A separate 100-pair run checked profiling overhead; runtime traces measured the new presentations against real clean and dirty Git states.

| Check | Result |
| --- | --- |
| Directory jumping with no configured implementation | Supplies z, records visits, ranks matches, preserves the current directory on a missing match, and reuses its database across sessions |
| Existing implementations | Preserves a directly sourced plugin, a custom function, an external executable, and the real OMZ z plugin without adding a second set of hooks |
| Disable setting | WSH_DISABLE_DIRECTORY_JUMP=1 leaves the default disabled |
| Completion and literal paths | Actual ZLE completion handles a spaced path; literal shell characters in recorded paths do not execute |
| Named themes | minimal, wakamex, robbyrussell, and agnoster all resolve through the launcher and validated runtime |
| Renderer correctness | Tests cover leading status arrows, branch label suffixes, clean/dirty segment backgrounds, missing Git segments, background resets, provider escaping, and rejected executable/invalid styling fields |
| Directory-jump native-readiness overhead | 100 pairs; median 2.364 ms, p90 2.810 ms; passes the fixed 3 ms p90 limit |
| Default profiling native-readiness overhead | 100 pairs; p90 2.103 ms; passes the fixed 3 ms limit |
| Runtime tracing overhead | Fresh 60-pair check; readiness p90 1.314 ms and worst-state refresh p90 0.249 ms; passes the existing 3 ms / 0.5 ms limits |
| Robbyrussell rendering in the traced workload | 60 snapshots; median 6.5 microseconds, p90 10 microseconds, maximum 19 microseconds |
| Agnoster rendering in the traced workload | 60 snapshots; median 8.5 microseconds, p90 14 microseconds, maximum 22 microseconds |

## Implementation and compatibility

The directory-jump source, completion, manual, and license are pinned byte-identical copies of OMZ plugins/z at commit 9112b53fa8b5ab556c7c893aa8be8a247ac512a0, derived from Zsh-z. The adapter uses a native single-command lookup and preserves existing implementations. Wsh compiles the source and installs the completion bytes under the _zshz function name expected by the upstream widget. It integrates with an existing compinit setup and does not initialize another completion framework. [Vendored provenance](../../third_party/zsh-z/PROVENANCE.md) and [component policy](../../VENDORED-COMPONENTS.md) record the transformations and ownership behavior.

The new theme definitions use the same Git collector. A bounded optional segment map supplies named background colors and trusted Powerline transitions; an optional Git label suffix supports parenthesized labels. The schema remains data-only and rejects unknown fields and executable values. Existing definitions without the new fields preserve their previous rendering behavior. [THEMES.md](../../THEMES.md) documents the ports, supported components, format, and Agnoster's Powerline glyph requirement. The ports do not reproduce executable OMZ components outside Wsh's current field set.

## Command lookup removed the startup bottleneck

The initial adapter failed the gate at 6.278 ms p90 extra startup. Excluding automatic visit recording left most of that cost. Function profiling and file tracing located the cost in the adapter, while confirming that compiled plugin code was loaded. An isolated comparison measured median command-table lookup at 3.584 ms versus 0.103 ms for whence. Replacing that lookup was the sole product intervention. The final adapter explicitly invokes builtin whence and retains directory recording and all upstream behavior.

[The diagnosis](diagnosis.md), [initial samples](directory-samples.tsv), [recording-exclusion samples](no-recording-samples.tsv), [isolated lookup samples](command-lookup.tsv), and [first whence comparison](whence-samples.tsv) preserve that experiment. The [final samples](accepted-directory-samples.tsv) and [summary](accepted-directory-summary.json) include every planned observation.

## Reproduction and retained evidence

The [plan](../builtins-themes-plan-2026-09-05.md) fixes scope and gates. [Metadata](metadata.json) records the exact commands, workload, enabled components, instrumentation modes, source and binary identities, target, build configuration, and host. The final unsigned development bundle is ac511dda378ed8d5ba9e4a10d33e6a49269b54f137ebc3e1e40391d2d87d86fe, from source 3decf521a13d98b9e0f50c64c666766406800205 plus the retained worktree changes. The [manifest](bundle-manifest.json.gz), [tracked diff](implementation.diff.gz), and [source/evidence hashes](SHA256SUMS) identify its inputs.

The [final host suite](final-host-suite.log.gz), [real OMZ directory-jump tests](final-omz-directory-jump.log), and [named-theme checks](final-named-themes.log) retain correctness results. The selected OMZ snapshot does not ship a standalone Zsh-z upstream test suite; Wsh tests the real vendored implementation directly.

[Profiling samples](accepted-profile-samples.tsv), [summary](accepted-profile-summary.tsv), and [gates](accepted-profile-gates.tsv) retain the final overhead check. [Runtime tracing samples](runtime-trace.tsv) were measured on the same runtime binary before the shell-only lookup change. [Renderer traces and summary](render-traces/summary.json) retain the four-theme measurements; those timings include trace instrumentation and are not an uninstrumented renderer benchmark.

Run python3 benchmarks/verify-builtins-themes-evidence.py to verify source hashes, regenerate summaries and gates, and check retained correctness results. Canonical glibc 2.28 validation, exact-head remote CI, and two-build reproduction were not rerun. No live configuration, commit, remote branch, or release was changed.
