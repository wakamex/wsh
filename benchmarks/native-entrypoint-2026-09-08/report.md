# Native startup removes manual configuration loading with a small code reduction

The native entrypoint is a promising direction for simpler startup ownership. It starts without user activation state, lets Zsh load user configuration directly, and preserves raw Zsh startup context and status. Against a small installation-owned Rust launcher, it removes seven net physical lines from the compared startup implementation and reduces paired median first-editor latency by 0.926 ms with an existing prompt and 0.810 ms with the minimal Wsh theme. Both prototypes passed direct login-style checks and 14 existing shell-contract checks each; the final native patch passed 75 upstream scripts with zero failures and two existing skips before 100 alternating startup pairs.

| First-editor workload, 50 starts per variant | Installation-owned launcher median | Installation-owned launcher p95 | Native entrypoint median | Native entrypoint p95 | Paired native-minus-launcher median | Paired native-minus-launcher p95 | Fixed paired p95 gate |
|---|---:|---:|---:|---:|---:|---:|---|
| Existing prompt, editing defaults and directory jumping | 25.464 ms | 26.210 ms | 24.610 ms | 25.337 ms | -0.926 ms | -0.312 ms | Pass, at most +3 ms |
| Minimal theme, local Rust runtime, editing defaults and directory jumping | 26.165 ms | 26.702 ms | 25.392 ms | 26.044 ms | -0.810 ms | -0.311 ms | Pass, at most +3 ms |

These are unsigned host prototypes. Production source selection, installations, account shells, and public CLI behavior remain unchanged. This experiment recommends a native entrypoint as the next integration direction; it does not establish a release-ready system installation or authorize a migration.

## Both installations remove activation dependence

The [launcher control](launcher.rs) resolves `bin/zsh` relative to its own executable, forwards native shell arguments, supplies the current startup environment, and executes that Zsh. It reads no user selection record. The [native patch](native-entrypoint.patch) resolves the installation from Zsh's existing executable identity and invokes installed setup around the engine's existing startup-file reader. It uses the same Rust runtime, bundled components, themes, and manager.

Direct tests execute both entrypoints with login argv[0], absent, malformed, incompatible, and chmod-zero activation files, shell-command strings using Zsh arrays, non-UTF-8 and empty argument bytes, checked exit statuses, scripts, and no-RCS flags. Both pass installation relocation and symlink-entrypoint checks. The no-HOME test uses `-f` to avoid reading the live account's configuration. A native executable copied without its optional integration still runs Zsh and diagnoses missing Wsh defaults.

The direct PTY fixture starts a local Rust theme runtime without activation, suspends a real sleep with Ctrl-Z, resumes it with `fg`, interrupts it with Ctrl-C, returns to the prompt with status 130, and exits with status 23. No account or installed shell was changed. These are fresh-home tests at the current user identity; a distinct account, complete GDM/PAM login, and reboot were not exercised.

## Native startup preserves configuration context

| Comparison with the exact raw Zsh control | Installation-owned launcher using current wrappers | Native prototype |
|---|---|---|
| Evaluation context inside `.zshenv`, `.zprofile`, `.zshrc`, and `.zlogin` | `file:file`, reflecting the wrapper's extra source layer | `file`, matching raw Zsh |
| Initial `$?` after absent or successful `.zshenv` | 1 in the tested cases | 0, matching raw Zsh |
| Initial `$?` after `.zshenv` ends with `false` | 1 | 1, matching raw Zsh |
| Global startup policy | Forces `-d`, as the current manager does | Honors native defaults and explicit `-d` |
| Redirected ZDOTDIR, RCS suppression, GLOBAL_RCS changes, user hooks, login/logout order | Existing configuration contract passes | Existing contract and isolated raw-Zsh comparisons pass |

The global-file comparison uses real files mounted over `/etc` in a private bubblewrap namespace. It covers ordinary login startup, explicit `-d`, user suppression of RCS, and user suppression of GLOBAL_RCS. Host files are unchanged. The launcher's forced `-d` is an existing policy that could also be changed in a launcher; it is not an inherent wrapper limitation. Likewise, a wrapper could preserve startup status with additional bookkeeping. Native integration gives those responsibilities a direct boundary around Zsh's existing reader.

The native adapter restores only transitional manager metadata rather than redirecting ZDOTDIR or saving and restoring RCS. The patch also preserves `lastval` around Wsh setup and profile events so optional integration does not overwrite the user's startup result. The linked [direct results](direct-results.json) and [boundary results](boundary-results.json) retain each comparison.

## Code reduction is modest

| Compared startup code, physical lines including comments and blanks | Launcher control | Native prototype |
|---|---:|---:|
| Zsh startup adapters | 168 across four redirecting startup files | 102 across three setup files |
| Separate Rust shell launcher | 29 | 0 |
| Net growth in upstream C source | 0 | 88, from 94 added and 6 replaced lines |
| Total additional startup code over the same upstream Zsh | 197 | 190 |

The native prototype deletes manual sourcing of user startup files and the ZDOTDIR/RCS restoration state machine. It retains ordinary Zsh integration for components, foreground startup, profiling, and prompt services. Seven fewer lines is a small reduction; the stronger result is restoring native startup semantics with one reader.

The unchanged Rust manager still serves verification, updates, rollback, doctor, profiling, and exact foreground startup. None of that code counts as deleted. The native adapter includes compatibility with the manager's current environment; a migration could remove some of it, but this experiment does not count hypothetical deletions.

Tracking the latest upstream revision and maintaining the two existing fixes already incur an upstream maintenance burden. This comparison adds one patch to `Src/init.c`, not an entirely new upstream tracking responsibility. It does introduce additional native behavior to review. No later-upstream rebase was attempted, so the experiment makes no claim about future conflict frequency.

## Correctness coverage and retained failures

Both variants passed history substring search, autosuggestions, syntax highlighting, plugin doctor, prompt ownership and nested shells, directory jumping, named themes, end-to-end profiling, delayed editor readiness, configuration coexistence, structured foreground startup, early terminal policy, manager login recovery, and terminal marker checks. Both variants also passed prompt ownership, nested shells, doctor cleanup advice, and directory jumping against the real Oh My Zsh checkout at `605a393f1c4734b23c6551370b9d542724e77879`, using its robbyrussell theme and git/z plugins. Two unrelated local theme modifications are identified in [the checkout record](real-omz.json), which also retains a complete checkout fingerprint and exact commands. The native upstream suite passed 75 scripts with zero failures and two existing skips. [Check records](checks-native.json) retain exact commands; compressed logs retain the observations.

The first prototype incorrectly freed a Zsh heap-allocated profiling string with the permanent allocator's free operation. Replacing that allocation with the matching permanent allocator fixed the crash, and end-to-end profiling passed. Its missing-integration warning also contaminated two upstream raw-Zsh tests; the diagnostic now applies to the branded `wsh` entrypoint while a raw `zsh` executable without Wsh payload remains quiet. Both failures and the original patch remain in `attempt-1/`.

The first common build used `/usr` without installing there, so raw-Zsh fixtures could not locate compiled module paths. Both variants were rebuilt with the same real private prefix. One relocation fixture explicitly sourced the deleted `.zshenv` wrapper; [its adapted copy](profile-native.zsh) changes that reference to the replacement early adapter and preserves the empty-module-path assertions. An initially failed directory-jump run passed the unchanged implementation under a diagnostic trace and in the final suite; no directory-jump intervention was made.

The terminal observer initially treated the secondary prompt during multiline input as an ordinary prompt. It then interrupted the next command while it was still being entered, producing nine prompt starts rather than ten. The retained transcript shows the truncated command. [The corrected observer](terminal.zsh) requires native `P;k=i` before the readiness marker, and both variants pass the original exact counts. The production observer is unchanged by this experiment. The new interactive harness was also renamed after its original `pty.py` filename shadowed Python's standard module.

A later raw-Zsh comparison exposed startup status being overwritten by both wrappers and the first native hooks. The final native hooks preserve that status; `attempt-2/` retains the earlier passing-contract implementation before this added check. A missing brace stopped the first incremental compilation of this correction; the error log is retained, and the corrected source was rebuilt before final correctness and timing. No timing occurred under a failed implementation or observer.

## Fixed measurement and reproducible inputs

The [plan](plan.md) fixes the counterfactual, 50 alternating pairs per presentation, and +3 ms paired p95 regression gate. Both builds use the locked `cad0d67c76e2be7371cf3526b79ea2581810d35a` archive, existing two source patches and test correction, the same compiler and configuration, and identical modules and Rust runtime. Native setup is the only additional engine patch. Prototype manifests list actual payload bytes and pass the existing manager's verifier; they identify development artifacts and do not constitute release provenance.

Timing runs fresh login-style shells on CPU 0 in an isolated home, with native global startup disabled in both variants for a matched workload. It ends at OSC 133 B after editor initialization. All 200 samples are retained; no builds, checks, or tool-shell commands overlap measurement. The parent verifies that each original process becomes the intended Zsh executable. Medians use the retained runner's nearest-rank convention; paired statistics subtract observations within the same round. The environment's filesystem caches are not flushed.

[Metadata](metadata.json), compressed manifests, `build-identities.json`, source snapshots, exact build logs, and SHA256SUMS identify the source base, local changes, native and Rust binaries, modules, compiler/configuration, enabled components, fixture, trace mode, commands, and host. [Samples](samples.json) and [summary](summary.json) retain the arithmetic. The shared evidence verifier checks identities, counts, semantics, terminal transcripts, and fixed gates without rerunning timing.

To reproduce in a fresh scratch location matching the runner, supply the pinned archive and source template bundle named in `build.py`, then run `python3 benchmarks/native-entrypoint-2026-09-08/build.py control` and `python3 benchmarks/native-entrypoint-2026-09-08/build.py native`. Run `direct.py`, `boundaries.py`, `interactive.py correctness`, and `checks.py launcher native` from the same directory through Python. Run `interactive.py measure` only after correctness and the upstream suite finish. The builder requires its declared private scratch installation; preserve an earlier run before reusing that location.

## Native entrypoint migration still needs a CLI and installation contract

The prototype's `bin/wsh` accepts native Zsh arguments. Existing management and exact foreground operations still work through the unchanged manager, as the regression suite verifies. They are not dispatched by the prototype's native `wsh`: `wsh update` would be a script invocation, and native `--` does not mean Wsh's existing exact foreground interface. A production design must choose a separate management entrypoint or retain explicit dispatch, update callers such as Wakterm, and count that code before claiming the final reduction.

A system installation must also keep the native executable, matching modules, and optional integration coherently available through updates. This experiment does not implement installation selection, package ownership, mixed-version updates, migration, or rollback of that installation. The canonical glibc 2.28 build and two-build reproducibility gate were not rerun for the prototype. Those are release acceptance work after the entrypoint and CLI design is chosen.

Prompt rendering and shell lifecycle remain local. This result introduces no cross-shell runtime, Git daemon, editor rewrite, or completion replacement.
