# Vendored component provenance and Wsh divergences

Wsh commits exact upstream runtime source so a release can build offline, reproduce its payload, expose the code receiving shell authority, and pair one tested plugin version with one tested Zsh build. Vendoring does not imply that Wsh rewrote or patched the component. This document records every build transformation, runtime policy, compatibility action, and behavior difference around vendored code.

The current plugin snapshots are byte-identical to their recorded upstream revisions. Wsh compiles additional `.zwc` files during the bundle build, retains the source and license, and loads the source through Wsh-owned adapters. The selected Zsh revision carries one separate digest-pinned source patch with a minimal reproducer and an explicit reason the fix belongs in the native producer.

All three interactive defaults come from repositories maintained by `zsh-users`. Oh My Zsh ships an opt-in copy of history substring search. Autosuggestions and syntax highlighting are separate projects commonly installed through Oh My Zsh's custom plugin directory. None is enabled by Oh My Zsh by default.

`wsh doctor` reuses the adapters' byte-exact ownership results. It recommends removing an external startup declaration only when that declaration loaded the pinned implementation already supplied by Wsh. Modified and unrecognized implementations stay active and receive no removal recommendation, disabled defaults produce no recommendation, and the command never rewrites startup source. The retained [plugin-doctor result](benchmarks/plugin-doctor-2026-09-03/report.md) tests these cases against the bundled source.

## Current divergence summary

| Component | Upstream source changes | Wsh behavior around the component | Classification |
|---|---|---|---|
| Zsh 5.9.2 | None | Used by official release `v0.1.3` and retained as the stable comparison baseline | Distribution build |
| Zsh `cad0d67c76e2be7371cf3526b79ea2581810d35a` | One compiled terminal-integration patch and one test-only fixture correction | Used by current development after passing the complete upstream and Wsh gates; built with `Util/preconfig` and packaged with its executable, modules, and functions | Narrow upstreamable source fix, distribution build, and compatibility policy |
| History substring search | None | Loads after user startup, binds advertised Up and Down sequences only when their active-map bindings are ordinary history navigation, replaces exact recognized upstream or Oh My Zsh runtime definitions, and preserves modified code or custom bindings | Product default and compatibility policy |
| Autosuggestions | None | Selects upstream's documented manual-rebind mode by default, loads after history widgets, replaces only an exact pending copy, and preserves active or modified implementations | Upstream-supported configuration and compatibility policy |
| Syntax highlighting | None | Defers clean loading until the first `precmd`, activates missing redraw hooks around an exact inactive copy, and preserves exact active, modified, incomplete, or custom implementations as described below | Wsh startup-integration fix |

## The post-5.9 Zsh revision has one source patch and one test correction

Pinned source: `zsh-users/zsh` commit `cad0d67c76e2be7371cf3526b79ea2581810d35a`, tree `2c07cbc91c766336de8029e0da8e34723bbe09bf`.

The source lock records the canonical repository, exact commit and tree, complete archive SHA-256, and each compiled-source patch digest. The bundle build applies source patches before upstream `Util/preconfig`, records their digests in the bundle manifest, and installs the resulting executable, modules, and functions used by Wsh. Git snapshots lack generated manuals and help files, so they are not part of this bundle payload.

The native terminal integration had two reproduced defects. Its OSC 133 prompt marker wrote a generated identifier at a fixed byte offset that overwrote the `aid=z` field name, so Wakterm's authoritative parser rejected every prompt start. Its initial OSC 7 report was coupled to an optional terminal query; Wsh disabled that query after measuring a 500 ms unanswered wait, which also removed the initial directory report and left a child application's remote OSC 7 value active after the child returned. Patch `build/zsh-patches/cad0d67c-terminal-integration.patch`, SHA-256 `b4c048789cac67a0b07d4d2644a8de266dafa279ac570a6419e5080403dfc5f8`, writes the identifier at its named placeholder and emits the current directory from the native prompt path. A wrapper could only mask these defects by installing a second lifecycle owner. The retained [native terminal-integration result](benchmarks/native-terminal-integration-2026-09-04/report.md) covers unpatched and patched transcripts, Wakterm's real parser, process counts, prompt-cycle latency, first foreground startup, and disable behavior.

Five upstream tests added after 5.9 attempted to suppress interactive prompts with command-prefix `PS1=` assignments, but both stable 5.9.2 and the pinned revision emit prompt bytes for those invocations. The digest-pinned correction changes only the affected `Test/` expectations, excludes no tests, and does not enter compiled or installed source. The source-patched revision passed 75 scripts with 0 failures and 2 existing skips. Wsh disables only the revision's ZLE terminal query by default when no explicit environment or `.zshenv` policy exists because unanswered queries otherwise add a 500 ms wait. The retained [edge-Zsh result](benchmarks/edge-zsh-2026-09-03/report.md) records the original source-selection experiment, while the terminal-integration report records the later source divergence and complete retest.

## History substring search adds binding and ownership policy

Pinned source: `zsh-users/zsh-history-substring-search` commit `14c8d2e0ffaee98f2df9850b19944f32546fdea5`.

The upstream component supplies ZLE widgets but leaves key selection to surrounding configuration. Wsh binds the terminal's advertised Up and Down sequences in the active `main` keymap only when the existing binding has ordinary history behavior. A custom binding remains authoritative. `WSH_DISABLE_HISTORY_SUBSTRING_SEARCH=1` leaves the default disabled.

When user startup has already loaded an exact pinned upstream or exact recognized Oh My Zsh copy, the adapter removes that copy's temporary highlight hooks and reloads the bundled definition so one runtime owner remains. The comparison is bounded and byte-exact. Modified or unknown definitions remain external. This takeover behavior belongs to Wsh and is not an upstream patch.

The retained [history-search result](benchmarks/history-substring-search-2026-09-03/report.md) covers the key behavior, ownership cases, process trace, and startup cost.

## Autosuggestions selects an upstream-supported mode

Pinned source: `zsh-users/zsh-autosuggestions` commit `85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5`.

Wsh sets upstream's documented `ZSH_AUTOSUGGEST_MANUAL_REBIND` option before loading the component. Widgets present at the first prompt are wrapped once instead of being rescanned on every prompt. A component that installs or replaces relevant widgets later must call the upstream `_zsh_autosuggest_bind_widgets` function, which the Wsh fixture tests. `WSH_AUTOSUGGEST_REBIND_MODE=automatic` restores upstream's automatic scanning, `WSH_AUTOSUGGEST_ASYNC=0` selects synchronous fetching, and `WSH_DISABLE_AUTOSUGGESTIONS=1` disables the default.

An exact copy that has only registered its pending first-prompt hook can be replaced before it wraps widgets. An active wrapper stack, modified source, or unknown implementation remains external because unwinding it would be ambiguous. These defaults and ownership rules are Wsh policy implemented around unchanged upstream source.

The retained [autosuggestions result](benchmarks/autosuggestions-2026-09-03/report.md) records the settled-prompt improvement, matched edit latency, ownership cases, cancellation, and process behavior.

## Syntax highlighting fixes Wsh startup timing

Pinned source: `zsh-users/zsh-syntax-highlighting` commit `2fc57d63067c18b1100ecdbf684fa5baf49459d1`.

The upstream redraw-hook path defines its hook functions and installs them only when the ZLE option is active while the source file runs. Wsh currently loads the user's `.zshrc` from inside its bundled startup file so it can preserve native configuration while installing trusted Wsh integration afterward. In that nested path, an ordinary user declaration ran while ZLE was inactive. The unchanged upstream source defined its functions and pre-exec hook but installed neither redraw nor finish hook, leaving syntax highlighting silently inactive.

This is a Wsh integration failure, not a general upstream bug. The clean Wsh path defers loading the unchanged bundled source until the first `precmd`, when ZLE is active. If user startup loaded the exact core and exact active shipped highlighters without installing redraw hooks, Wsh installs the upstream hook functions around that existing copy rather than parsing a second copy. Exact copies with complete hooks remain external owners. Modified active files, custom active highlighters, incomplete installations, and unknown implementations also remain external.

`WSH_DISABLE_SYNTAX_HIGHLIGHTING=1` disables the default. Upstream `ZSH_HIGHLIGHT_HIGHLIGHTERS` and `ZSH_HIGHLIGHT_STYLES` configuration remains authoritative.

The retained [syntax-highlighting result](benchmarks/syntax-highlighting-2026-09-03/report.md) reproduces the inactive-hook path, compares it with correctly initialized direct upstream, runs the upstream suite against bundled runtime files, and covers redraw semantics and composition.

## Vendored updates require a divergence review

Every vendored update must:

1. Record the upstream repository, revision, license, file list, and exact source digests in its provenance file.
2. Confirm whether any vendored byte differs from upstream and describe every patch separately.
3. Recheck each Wsh-selected upstream option and every adapter-owned load, binding, hook, takeover, disable, and fallback behavior.
4. Run the authoritative upstream test suite when it exists.
5. Rerun the retained Wsh correctness, composition, process, startup, prompt, edit, and floor-bundle gates that apply.
6. Update this document when a divergence is added, removed, or moved upstream.
7. For each Zsh identity, link the exact upstream `NEWS`, incompatibility notes, and commit comparison, then summarize only the capabilities and compatibility treatments Wsh directly tests.

A Wsh workaround should be deleted when an upstream release or a simpler startup contract removes its reproducer. Historical benchmark reports continue to describe the exact revisions they measured.
