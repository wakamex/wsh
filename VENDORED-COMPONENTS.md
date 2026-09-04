# Vendored component provenance and Wsh divergences

Wsh commits exact upstream runtime source so a release can build offline, reproduce its payload, expose the code receiving shell authority, and pair one tested plugin version with one tested Zsh build. Vendoring does not imply that Wsh rewrote or patched the component. This document records every build transformation, runtime policy, compatibility action, and behavior difference around vendored code.

The current plugin snapshots are byte-identical to their recorded upstream revisions. Wsh compiles additional `.zwc` files during the bundle build, retains the source and license, and loads the source through Wsh-owned adapters. A source patch would require a separate patch file, upstream and resulting digests, a minimal reproducer, and an explicit reason it cannot remain in the adapter.

All three interactive defaults come from repositories maintained by `zsh-users`. Oh My Zsh ships an opt-in copy of history substring search. Autosuggestions and syntax highlighting are separate projects commonly installed through Oh My Zsh's custom plugin directory. None is enabled by Oh My Zsh by default.

## Current divergence summary

| Component | Upstream source changes | Wsh behavior around the component | Classification |
|---|---|---|---|
| Zsh 5.9.2 | None | Used by official release `v0.1.3` and retained as the stable comparison baseline | Distribution build |
| Zsh `cad0d67c76e2be7371cf3526b79ea2581810d35a` | None in compiled or installed source; one test-only fixture correction | Used by current development after passing the complete upstream and Wsh gates; built with `Util/preconfig` and packaged with its executable, modules, and functions | Distribution build and compatibility policy |
| History substring search | None | Loads after user startup, binds advertised Up and Down sequences only when their active-map bindings are ordinary history navigation, replaces exact recognized upstream or Oh My Zsh runtime definitions, and preserves modified code or custom bindings | Product default and compatibility policy |
| Autosuggestions | None | Selects upstream's documented manual-rebind mode by default, loads after history widgets, replaces only an exact pending copy, and preserves active or modified implementations | Upstream-supported configuration and compatibility policy |
| Syntax highlighting | None | Defers clean loading until the first `precmd`, activates missing redraw hooks around an exact inactive copy, and preserves exact active, modified, incomplete, or custom implementations as described below | Wsh startup-integration fix |

## The post-5.9 Zsh revision has one test-only correction

Pinned source: `zsh-users/zsh` commit `cad0d67c76e2be7371cf3526b79ea2581810d35a`, tree `2c07cbc91c766336de8029e0da8e34723bbe09bf`.

The source lock records the canonical repository, exact commit and tree, and complete archive SHA-256. The bundle build runs upstream `Util/preconfig`, compiles unchanged Zsh source, and installs the executable, modules, and functions used by Wsh. Git snapshots lack generated manuals and help files, so they are not part of this bundle payload.

Five upstream tests added after 5.9 attempted to suppress interactive prompts with command-prefix `PS1=` assignments, but both stable 5.9.2 and the pinned revision emit prompt bytes for those invocations. The digest-pinned correction changes only the affected `Test/` expectations, excludes no tests, and does not enter compiled or installed source. The corrected revision passed 75 scripts with 0 failures and 2 existing skips. Wsh also disables the revision's ZLE terminal query by default when no explicit environment or `.zshenv` policy exists because unanswered queries otherwise add a 500 ms wait. The retained [edge-Zsh result](benchmarks/edge-zsh-2026-09-03/report.md) records the reproducer, counterfactual, complete test result, source identities, and performance gates.

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

A Wsh workaround should be deleted when an upstream release or a simpler startup contract removes its reproducer. Historical benchmark reports continue to describe the exact revisions they measured.
