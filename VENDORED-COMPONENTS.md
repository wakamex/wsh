# Vendored component provenance and Wsh divergences

Wsh commits exact upstream runtime source so a release can build offline, reproduce its payload, expose the code receiving shell authority, and pair one tested plugin version with one tested Zsh build. Vendoring does not imply that Wsh rewrote or patched the component. This document records every build transformation, runtime policy, compatibility action, and behavior difference around vendored code.

The current plugin snapshots are byte-identical to their recorded upstream revisions. Wsh compiles additional `.zwc` files during the bundle build, retains the source and license, and loads the source through Wsh-owned adapters. The selected Zsh revision carries three separate digest-pinned source patches with minimal reproducers and explicit reasons the fixes belong in the native producer.

History substring search, autosuggestions, and syntax highlighting come from repositories maintained by `zsh-users`. Directory jumping uses the pinned Zsh-z copy distributed by Oh My Zsh. Oh My Zsh ships an opt-in copy of history substring search. Autosuggestions and syntax highlighting are separate projects commonly installed through Oh My Zsh's custom plugin directory. None is enabled by Oh My Zsh by default.

`wsh doctor` reuses the adapters' byte-exact ownership results. It recommends removing an external startup declaration only when that declaration loaded the pinned implementation already supplied by Wsh. Modified and unrecognized implementations stay active and receive no removal recommendation, disabled defaults produce no recommendation, and the command never rewrites startup source. The retained [plugin-doctor result](benchmarks/plugin-doctor-2026-09-03/report.md) tests these cases against the bundled source.

## Current divergence summary

| Component | Upstream source changes | Wsh behavior around the component | Classification |
|---|---|---|---|
| Zsh 5.9.2 | None | Used by official release `v0.1.3` and retained as the stable comparison baseline | Distribution build |
| Zsh `cad0d67c76e2be7371cf3526b79ea2581810d35a` | Three compiled source patches and one test-only fixture correction | Used by current development after passing the complete upstream and Wsh gates; built with `Util/preconfig` and packaged with its executable, modules, and functions | Narrow upstreamable source fixes, distribution build, and compatibility policy |
| History substring search | None | Loads after user startup, binds advertised Up and Down sequences only when their active-map bindings are ordinary history navigation, replaces exact recognized upstream or Oh My Zsh runtime definitions, and preserves modified code or custom bindings | Product default and compatibility policy |
| Autosuggestions | None | Selects upstream's documented manual-rebind mode by default, loads after history widgets, replaces only an exact pending copy, and preserves active or modified implementations | Upstream-supported configuration and compatibility policy |
| Directory jumping | None | Loads directory jumping only when the selected command is absent and preserves existing implementations. Native builds generate a precompiled adapter from pinned Zsh-z with C data/query ownership; legacy builds retain the full plugin. Both install the completion source under its widget function name | Product default, build transformation, and compatibility policy |
| Syntax highlighting | None | Defers clean loading until the first `precmd`, activates missing redraw hooks around an exact inactive copy, and preserves exact active, modified, incomplete, or custom implementations as described below | Wsh startup-integration fix |

## The post-5.9 Zsh revision has three source patches and one test correction

Pinned source: `zsh-users/zsh` commit `cad0d67c76e2be7371cf3526b79ea2581810d35a`, tree `2c07cbc91c766336de8029e0da8e34723bbe09bf`.

The source lock records the canonical repository, exact commit and tree, complete archive SHA-256, and each compiled-source patch digest. The bundle build applies source patches before upstream `Util/preconfig`, records their digests in the bundle manifest, and installs the resulting executable, modules, and functions used by Wsh. Git snapshots lack generated manuals and help files, so they are not part of this bundle payload.

The native terminal integration had two reproduced defects. Its OSC 133 prompt marker wrote a generated identifier at a fixed byte offset that overwrote the `aid=z` field name, so Wakterm's authoritative parser rejected every prompt start. Its initial OSC 7 report was coupled to an optional terminal query; Wsh disabled that query after measuring a 500 ms unanswered wait, which also removed the initial directory report and left a child application's remote OSC 7 value active after the child returned. Patch `build/zsh-patches/cad0d67c-terminal-integration.patch`, SHA-256 `b4c048789cac67a0b07d4d2644a8de266dafa279ac570a6419e5080403dfc5f8`, writes the identifier at its named placeholder and emits the current directory from the native prompt path. A wrapper could only mask these defects by installing a second lifecycle owner. The retained [native terminal-integration result](benchmarks/native-terminal-integration-2026-09-04/report.md) covers unpatched and patched transcripts, Wakterm's real parser, process counts, prompt-cycle latency, first foreground startup, and disable behavior.

Zsh's compiled-function writer rounded each program to a whole word and wrote the rounded length from a heap allocation, including up to three bytes after the initialized program. Two isolated Wsh builds therefore produced different `.zwc` bytes from identical source, and those bytes could contain stale heap data. Patch `build/zsh-patches/cad0d67c-zcompile-padding.patch`, SHA-256 `d1da8d32b8afa27bb0516c81f63345ea1196edf177bdae151fe9f2ad617776a6`, writes the initialized program length followed by explicit zero padding. The bundle suite compiles the same fixture in two isolated directories, checks byte equality, and checks both byte-order copies for zero padding. The complete two-build gate compares manifests, archives, launchers, installers, and bootstrap scripts.

Five upstream tests added after 5.9 attempted to suppress interactive prompts with command-prefix `PS1=` assignments, but both stable 5.9.2 and the pinned revision emit prompt bytes for those invocations. The digest-pinned correction changes only the affected `Test/` expectations, excludes no tests, and does not enter compiled or installed source. The source-patched revision passed 75 scripts with 0 failures and 2 existing skips. Wsh disables only the revision's ZLE terminal query by default when no explicit environment or `.zshenv` policy exists because unanswered queries otherwise add a 500 ms wait. The retained [edge-Zsh result](benchmarks/edge-zsh-2026-09-03/report.md) records the original source-selection experiment, while the terminal-integration report records the later source divergence and complete retest.

The separate [native-entrypoint prototype](benchmarks/native-entrypoint-2026-09-08/report.md) adds startup hooks to `Src/init.c` and replaces redirecting startup files with three setup adapters. Its final host build passed all 75 upstream scripts with zero failures and two existing skips, plus the retained Wsh contract checks. This experimental patch is retained with its source and binary identities under `benchmarks/`; it is not in the production source lock or release patch queue. It tests whether native startup ownership can remove compatibility glue while keeping the Rust manager and runtime unchanged.

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

The native C runtime uses [tomlc17](third_party/tomlc17/PROVENANCE.md). Its source snapshot remains unchanged; a private build copy receives three recorded allocator/numeric compatibility changes. Wsh enables strict UTF-8 and full unsigned-64-bit theme thresholds. [Definition, upstream-parser and renderer comparisons](benchmarks/native-render-2026-09-08/theme-parser-report.md) pass. Native installations include its license. The legacy distribution retains its Rust runtime.

The native C runtime uses unchanged [yyjson](third_party/yyjson/PROVENANCE.md) source for strict JSON with full-u64 counters. Wsh owns protocol field/type/duplicate checks and resource bounds. Its upstream parser suite, [renderer parity](benchmarks/native-render-2026-09-08/renderer-report.md) and [complete-runtime contracts](benchmarks/native-render-2026-09-08/runtime-report.md) pass. Native installations include its license.

Every vendored update must:

1. Record the upstream repository, revision, license, file list, and exact source digests in its provenance file.
2. Confirm whether any vendored byte differs from upstream and describe every patch separately.
3. Recheck each Wsh-selected upstream option and every adapter-owned load, binding, hook, takeover, disable, and fallback behavior.
4. Run the authoritative upstream test suite when it exists.
5. Rerun the retained Wsh correctness, composition, process, startup, prompt, edit, and floor-bundle gates that apply.
6. Update this document when a divergence is added, removed, or moved upstream.
7. For each Zsh identity, link the exact upstream `NEWS`, incompatibility notes, and commit comparison, then summarize only the capabilities and compatibility treatments Wsh directly tests.

A Wsh workaround should be deleted when an upstream release or a simpler startup contract removes its reproducer. Historical benchmark reports continue to describe the exact revisions they measured.

## Directory jumping preserves an existing command

Wsh vendors OMZ `plugins/z` at commit `9112b53fa8b5ab556c7c893aa8be8a247ac512a0`, derived from agkozak/zsh-z. Runtime, completion source, MIT license, and manual remain byte-identical; [provenance](third_party/zsh-z/PROVENANCE.md) records their hashes. The build precompiles the runtime and installs OMZ's `_z` completion bytes as `_zshz`, the function name called by this snapshot's widget. The adapter registers that completion when compdef is already available. It does not initialize compinit.

The adapter runs after user startup and loads only when the selected command name, zshz function, and legacy _z function are absent. Existing aliases, functions, executables, and OMZ hooks remain active without takeover. `WSH_DISABLE_DIRECTORY_JUMP=1` disables this default. Upstream database ranking, locking, persistence, command options, background visit recording, and tab-widget behavior are unchanged. The selected OMZ snapshot contains no standalone upstream test suite; Wsh's real-component tests exercise ranking, persistence, spaces, literal shell characters, completion, automatic visit recording, disable behavior, and native/OMZ/custom ownership.

The complete C helper now uses both parsers under the same pinned configurations. Its protocol, lifecycle, real-Git and native-installation checks pass; [the complete-helper report](benchmarks/native-render-2026-09-08/runtime-report.md) records the explicit NUL-path boundary and remaining adoption work. Production dependency selection remains unchanged.

## Native compinit registration

The native development build adds `cad0d67c-native-completion.patch`, which replaces only compinit's cold registration loop with the native scanner when its builtin is available. The original loop remains the fallback for regular Zsh. Security auditing, cache validation, completion definitions and widgets remain upstream-owned. The [installed qualification](benchmarks/native-adoption-2026-09-10/completion/report.md) retains full upstream build tests, normal/sanitized registration and editor checks, a DEBUG-trap lifetime regression, and both failed and passing timing experiments. The legacy release source lock is unchanged.

## Native history ownership

Native development builds now select the [qualified C history owner](benchmarks/native-adoption-2026-09-10/history/report.md). Zsh retains public settings, conservative widget registration, editor operations and highlighter composition. C owns search state, matching, navigation and search-region updates. The exact pinned plugin remains available for recognized-copy comparison and legacy builds. Normal and sanitizer editor comparisons, installed ownership/composition tests and paired editing/startup gates pass.

The [native directory qualification](benchmarks/native-directory-final-2026-09-10/installed-report.md) retains vendor source bytes and replaces the data/query function only in a generated native adapter. Tests cover query and mutation behavior, confirmation, actual bind mounts and locks, mixed writers, lifecycle, custom cd, unload, actual completion and OMZ coexistence, plus sanitizer and startup gates.

## Complete autosuggestion controller prototype

The [complete controller experiment](benchmarks/native-consolidation-2026-09-10/autosuggestions-report.md) moves strategies, asynchronous collection, widget registration and editor actions into a private C module. Its generated fixture retains upstream configuration and small ZLE/completion bridges; the C source retains the upstream MIT notice. Vendored source bytes and selected runtime remain unchanged. Ten normal and sanitized editor modes pass, including sync/async completion, plus cancellation and response bounds. The large-history complete editing sequence improves 27.1%; installed coexistence and floor qualification remain prerequisites for adoption.

## Substantial highlighting parser prototype

The [parser ownership experiment](benchmarks/native-consolidation-2026-09-10/highlighting-report.md) replaces the main command-list parser only in a generated private fixture. C owns traversal and parser state while retaining Zsh tokenization, command classification and style helpers. Vendored bytes and the installed highlighter remain unchanged. The candidate passes 117/271 main fixtures and all 16 other fixtures, with identical normal/sanitized counts. Multiline and composed-region failures prevent adoption; rejected redraw measurements are retained without a performance claim.

## Installed native autosuggestion ownership

The [installed qualification](benchmarks/native-autosuggestions-installed-2026-09-10/report.md) supersedes the prototype adoption deferral. Native installations compile the complete C controller into the shell and generate thin Zsh configuration/completion callbacks. The upstream MIT notice is retained in the C source; pinned vendor bytes remain unchanged for exact-copy recognition. Existing active/modified ownership and user settings are preserved, including manual and automatic rebinding. Installed normal/sanitized editor, lifecycle, OMZ, startup and canonical floor checks pass. The large-history complete sequence improves 29.3%. The report separately records existing sanitizer-suite and terminal-doctor failures.

## Neutral highlight ownership in Zsh

The local [neutral-attribute parser fix](UPSTREAM-ZSH-BUGS.md#neutral-highlight-attributes-discard-ownership-metadata) restores `none` serialization round trips, including following memo and layer fields. This fixes stale syntax-highlighting regions in the existing plugin without changing its vendored bytes. The [retained reproduction](benchmarks/zsh-highlight-none-2026-09-10/report.md) compares identical upstream implementations in real ZLE and validates the native fix.
