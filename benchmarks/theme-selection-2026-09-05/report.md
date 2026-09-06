# Explicit Wsh theme selection replaces the prompt toggle

An explicit `WSH_THEME` now selects Wsh's prompt; leaving it unset or empty preserves the existing prompt. The full host suite and 40 shared-configuration cases passed, including real Oh My Zsh, nested regular Zsh, both bundled themes, a custom path containing spaces, and invalid definitions. The existing profiling-overhead gate passed at 2.897 ms p90 against its 3 ms limit over 100 paired observations.

The tests launched the real bundled Zsh under PTYs and checked startup values, prompt ownership, runtime hooks, aliases, nested shells, and profile reports. Doctor checks used the real OMZ loader before and after the documented theme-skip conditional.

| Check | Result |
| --- | --- |
| Unset or empty WSH_THEME | Existing prompt retained; no Wsh prompt runtime or prompt hooks |
| Bundled minimal and wakamex names | Each theme starts one Wsh runtime; profile reports confirm the selected identity |
| Custom definition path containing spaces | Loaded the custom-selection definition and confirmed its identity through the production profile parser |
| Missing or invalid definition | Diagnostic emitted; no Wsh prompt hooks installed; the prompt from user startup remains in place |
| Shared native and real OMZ configurations | 20 cases each, covering login and non-login startup, selection, errors, and four profiling variants |
| Nested regular Zsh | WSH_THEME is absent, even after startup files export it; the OMZ theme remains enabled |
| Doctor and OMZ | Configured overlap receives conditional-loading advice; resolved overlap and existing ownership receive no prompt cleanup advice; configuration hashes remain unchanged |
| Foreground startup with no selected theme | Exact argv, Ctrl-C, Ctrl-Z, fg, terminal state, repeated launch, and prompt return passed |
| Complete host suite | Rust, relocated bundle, editing features, runtime, startup compatibility, profiling, foreground, and native terminal checks passed |
| Native-readiness instrumentation overhead | 100 paired observations; median 2.039 ms, p90 2.897 ms; unchanged 3 ms p90 gate passed |

## Selection and OMZ behavior

The launcher and doctor no longer inject the bundle's default theme into the environment. Wsh consumes an explicit theme locally and resolves `minimal`, `wakamex`, or a definition path at runtime startup. Runtime hooks are installed only after the selected definition has started successfully. The separate public WSH_PROMPT selector has been removed; the internal prompt-owner diagnostic remains.

OMZ still loads according to the user's ZSH_THEME assignment. The [README conditional](../../README.md#prompt-selection), placed after that assignment and before sourcing OMZ, skips only the OMZ theme when WSH_THEME is nonempty. Plugins, aliases, and completions continue to load. Wsh does not intercept the OMZ loader, rewrite startup configuration, or unload arbitrary theme hooks. A failed definition cannot restore an OMZ theme that the user's conditional already skipped; the failure preserves the prompt as it stood after user startup.

## Evidence and reproduction

The [plan](../theme-selection-plan-2026-09-05.md) records the selected policy and fixed gates. This supersedes the public toggle from the [previous prompt-ownership experiment](../prompt-ownership-2026-09-05/report.md), whose exact inputs remain in accepted-source snapshots. The previous launcher unconditionally replaced WSH_THEME with the bundle default; the retained source diff records removal of those assignments.

The tested bundle is `33810a1d902cf1ffb4cc56dc803947517541d3c075114aec52d4f59d1979d0ae`, an unsigned development artifact from source `3decf521a13d98b9e0f50c64c666766406800205` plus the recorded worktree changes. [Metadata](metadata.json) records commands, source and binary identities, build configuration, OMZ pin, fixture, trace modes, and ordering. The [bundle manifest](bundle-manifest.json.gz) and [source and evidence hashes](SHA256SUMS) identify the tested inputs.

The [native configuration log](correctness.log), [real OMZ log](omz-correctness.log), [existing-prompt foreground log](foreground-existing.log), and [complete host suite log](host-suite.log.gz) retain correctness results. The focused test was subsequently expanded to check a spaced custom path and verify the actual theme identities through profile reports; those expanded cases passed separately on the same bundle.

[Raw timing samples](profile-samples.tsv), the [regenerated summary](profile-summary.tsv), and [fixed gates](profile-gates.tsv) retain the native-readiness check. The two isolated-runtime trace gates reuse historical samples because the runtime binary hash is unchanged. This experiment makes no new runtime speed claim.

Run `./benchmarks/verify-theme-selection-evidence.zsh` to verify hashes, reproduce summary arithmetic and gates, and check the retained correctness results. The canonical glibc 2.28 container suite and remote CI were not rerun. Live user configuration, remote branches, and releases remain unchanged.
