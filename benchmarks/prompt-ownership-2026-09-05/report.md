# Explicit prompt ownership preserves shared Zsh configuration

Wsh now preserves the user's existing prompt by default. `WSH_PROMPT=wsh` explicitly enables Wsh presentation and its Git collector. Shared native and real Oh My Zsh configurations passed 24 startup and profiling cases; doctor suggested conditional theme loading only for the configured OMZ overlap. The native-readiness profiling gate passed at 2.521 ms p90 overhead against the unchanged 3 ms threshold.

The tests launched real bundled Zsh under PTYs, checked prompt and hook ownership, exercised nested regular Zsh, and ran doctor before and after the documented OMZ conditional. Both modes retain aliases and editing integrations. Existing mode has no Wsh prompt runtime or runtime hooks; Wsh mode has one runtime and one prompt hook.

| Check | Result |
| --- | --- |
| Shared native configuration | 12 cases passed: regular Zsh, default Wsh, explicit existing and Wsh modes, invalid selector, login startup, and both profiling modes |
| Shared real OMZ configuration | The same 12 cases passed with the real loader, robbyrussell theme, and Git plugin |
| Nested regular Zsh | Retains its theme; Wsh revokes selector exports introduced in `.zshrc` and `.zlogin` |
| Doctor with Wsh ownership and a configured OMZ theme | Suggests the conditional before OMZ loading, explains that the selector alone does not skip the theme, and offers existing mode |
| Doctor after conditional loading or with existing ownership | No prompt cleanup suggestion; startup file hashes remain unchanged |
| Foreground application return in existing mode | Exact argv, Ctrl-C, Ctrl-Z, `fg`, terminal state, startup files, and repeated launch checks passed |
| Full host suite | Rust, relocated bundle, plugin, runtime, startup compatibility, profiling, foreground, and native terminal tests passed |
| Native readiness instrumentation overhead, 100 paired observations | Median 1.947 ms; p90 2.521 ms; passes the existing 3 ms p90 gate |

## Configuration behavior

`WSH_PROMPT` is available before user startup, defaults to `existing`, and is not exported to child shells. The prompt implementation is selected after `.zshrc`. Invalid nonempty values produce a diagnostic and preserve the existing prompt. The variable is a startup selector; changing it later does not switch an active renderer. Command-local selection applies to `run`, bare startup, foreground startup, profiling, and doctor.

The [README](../../README.md#prompt-selection) documents the conditional after the user's existing `ZSH_THEME` assignment and before sourcing OMZ. This preserves ordinary Zsh behavior. Doctor reports a configured OMZ theme when the real loader's `_omz_source` function is present and Wsh owns the renderer. It does not claim to reconstruct every executed theme or remove arbitrary hooks. Redundant-plugin advice also preserves conditional declarations for regular Zsh.

## Reproduction and retained inputs

The [plan](../prompt-ownership-plan-2026-09-05.md) fixes the scope and gates. [Metadata](metadata.json) records commands, source and binary identities, build configuration, fixture, instrumentation, and ordering. The source revision is `3decf521a13d98b9e0f50c64c666766406800205` plus the recorded worktree changes. The tested bundle is `73780b6195fe92fe85184875da78bd33aee49521e5f12c39dcf650910410b7ac`, an unsigned development artifact. Its [manifest](bundle-manifest.json.gz) binds the exact payload; [SHA256SUMS](SHA256SUMS) binds changed source and evidence files.

The real OMZ checkout is pinned to `9112b53fa8b5ab556c7c893aa8be8a247ac512a0`. All 1,096 tracked blobs were compared with that Git tree. The tests use its real loader, libraries, Git plugin, and robbyrussell theme. The standard suite has no external OMZ download requirement; its test accepts the real checkout as an optional third argument for this retained experiment.

The [native configuration log](correctness.log), [OMZ log](omz-correctness.log), [existing-prompt foreground log](foreground-existing.log), and [complete host suite log](host-suite.log.gz) retain correctness results. The [baseline reproducer](baseline-reproducer.log.gz) fails against the prior bundle because the selector is unavailable during startup; that bundle also activates its renderer by default. Early test-observer corrections are recorded in metadata. They changed the observer, not the product.

The [raw timing samples](profile-samples.tsv), [summary](profile-summary.tsv), and [gates](profile-gates.tsv) retain the performance check. An initial invocation supplied half the intended repetition count; its [50-pair samples](short-run-samples.tsv) are retained separately. The accepted invocation uses the planned 100 pairs and excludes none. Historical isolated-runtime trace gates are reused explicitly because the runtime binary hash is unchanged; this change does not claim a new runtime latency improvement.

Run `./benchmarks/verify-prompt-ownership-evidence.zsh` to verify hashes, regenerate the timing summary and gates, and check retained correctness results. The canonical glibc 2.28 container suite and remote CI were not rerun. No live user configuration, release, or remote branch was changed.
