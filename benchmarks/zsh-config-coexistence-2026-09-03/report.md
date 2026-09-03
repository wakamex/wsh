# Existing Zsh configuration loads correctly, while some legacy themes retain material duplicate work

The startup adapter now loads existing user startup files once in native order before `wsh` integration. Plain managed startup added 0.865 ms at p90 over the same configuration with direct integration, below the fixed 1 ms gate. Aliases, existing hooks, Oh My Zsh, history substring search, autosuggestions, and syntax highlighting remained active in the tested combinations. Legacy theme appearance did not remain active because the current `wsh` renderer owned the displayed prompt.

Retained theme machinery was selectively material. A trivial prompt transition used the expected one `wsh` Git process with no Oh My Zsh theme, agnoster, or the three ZLE plugins. Robbyrussell retained five additional Git processes and Wakamex retained one. The first adapter therefore preserves user configuration and one `wsh` owner but does not attempt to unload theme code or unregister hooks. A generic suppression rule is not accepted.

The baseline ran the current clean source revision and development bundle `cdf7d443efdfac9d9f0c8a9aa8cc9778ef15f2a43666d734372c819a6d4ffa13`. Its non-interactive, interactive, and login cases all passed the expected failing assertion that user startup configuration was missing. The intervention used development bundle `11fef8d12d8553db2a3df7bfa09b91059ca0c78f20a922cfc76b92734f944c20`; exact payload and fixture identities are retained in [`metadata.txt`](metadata.txt).

## Startup results

Each variant ran 5 warmups followed by 20 forward-order and 20 reverse-order launches pinned to CPU 0. Timing began before PTY creation and ended at the first editable prompt. The plain direct variant sourced the same plain `.zshrc` and `wsh` integration without the manager or bundle startup adapter. Existing configuration costs remain visible rather than being attributed to the adapter.

| Variant | Median, ms | p90, ms | Maximum, ms | p90 difference from relevant base |
|---|---:|---:|---:|---:|
| Plain direct integration | 7.079 | 7.287 | 7.540 | Base |
| Plain managed startup | 7.939 | 8.152 | 8.454 | +0.865 vs direct |
| Empty user configuration | 7.931 | 8.111 | 8.671 | Base |
| Oh My Zsh without a theme or plugins | 44.671 | 45.227 | 50.637 | +37.115 vs empty |
| Oh My Zsh with agnoster | 45.283 | 45.679 | 51.063 | +0.453 vs OMZ base |
| Oh My Zsh with Wakamex | 48.659 | 49.079 | 49.727 | +3.853 vs OMZ base |
| Oh My Zsh with robbyrussell | 54.518 | 55.032 | 55.684 | +9.806 vs OMZ base |
| Oh My Zsh with three ZLE plugins | 67.645 | 68.433 | 69.088 | +23.206 vs OMZ base |
| Oh My Zsh with Wakamex and three ZLE plugins | 71.820 | 72.370 | 72.856 | +27.143 vs OMZ base |

The adapter comparison passes its fixed startup threshold. The Oh My Zsh and plugin values are current costs for these pinned configurations, not costs introduced by the adapter and not estimates of a later bundled implementation.

A process-only `strace` comparison recorded `zsh`, `wsh-runtime`, and the expected initial `git` scan in both direct and managed startup. The managed path added only the initial `wsh` launcher executable, which replaced itself with Zsh. The startup adapter launched no external helper and left no additional process.

## Ownership and process results

Clean archives from the pinned upstream commits supplied every external fixture. Each variant loaded through the managed startup path in the same Git repository. The harness verified the user alias, active runtime, displayed prompt owner, requested ZLE widgets, hook arrays, and Git executions after one trivial prompt transition.

| Variant | Displayed prompt | Wsh hooks | ZLE defaults | Git processes per trivial transition | Retained competing machinery |
|---|---|---|---|---:|---|
| OMZ without theme or plugins | wsh | One each | None requested | 1 | OMZ async and terminal-support hooks |
| robbyrussell | wsh | One each | None requested | 6 | OMZ shared async Git collection and terminal-support hooks |
| agnoster | wsh | One each | None requested | 1 | OMZ terminal-support hooks; its prompt expressions were no longer rendered |
| Wakamex | wsh | One each | None requested | 2 | Wakamex prompt, Git request, worker shutdown, and OMZ terminal-support hooks |
| Three ZLE plugins | wsh | One each | All three loaded | 1 | Plugin-owned ZLE and highlighting hooks plus OMZ terminal-support hooks |
| Wakamex and three ZLE plugins | wsh | One each | All three loaded | 2 | Both plugin and Wakamex hooks plus OMZ terminal-support hooks |

Robbyrussell and Wakamex cross the predeclared materiality gate by adding child processes whose results do not own the displayed prompt. Agnoster does not cross the prompt-transition gate in this composition because replacing `PROMPT` prevents its synchronous expressions from running. The three ZLE plugins add startup time, but they provide requested behavior and are not duplicate `wsh` implementations in this experiment.

## Startup-file and hook correctness

The regression fixture covers non-interactive, interactive non-login, and interactive login shells. A user `.zshenv` changes `ZDOTDIR`; later `.zprofile`, `.zshrc`, `.zlogin`, and `.zlogout` files load from the changed directory in native order. Aliases survive, user `precmd`, `preexec`, and `zshexit` hooks remain ahead of the appended `wsh` hooks, sourcing `wsh` integration twice still registers one owner, and command failure, prompt refresh, login exit, and runtime cleanup remain functional. A separate case disables `RCS` in `.zshenv`; later user startup files stay disabled while the required bundle integration loads, and the user's final option state is restored.

The launcher always passes `-d` before user arguments so an explicit `wsh run -- -l` retains the bundle's global-startup isolation. It records the incoming `ZDOTDIR`, falling back to `HOME`, before selecting the bundle adapter. A launch inherited from an older `wsh` session recognizes that session's bundle `ZDOTDIR` and falls back to its recorded user directory or `HOME`.

The complete glibc 2.28 floor build then repeated the Rust suite, upstream Zsh suite, relocated-bundle verification, real provider request, PTY runtime lifecycle, configuration coexistence regression, dynamic-library comparison, and maximum-symbol check. Floor bundle `893cb3da9515fb47cec7290bd6b167e26f4b5ef85117cba3e04bf0478e0f1ca0` passed with `GLIBC_2.28` as its newest imported symbol.

## Duplicate suppression remains a separate decision

Arbitrary theme files can define aliases, functions, options, hooks, workers, and unrelated behavior in addition to a prompt. Unloading them after `.zshrc` or preventing them from loading based only on `ZSH_THEME` could remove behavior the user intended. The accepted adapter therefore makes no such change.

The next safe mechanism should distinguish presentation choice from executable compatibility. An explicit legacy-theme mode can leave the selected theme in charge and omit the `wsh` renderer. A `wsh` presentation mode can recommend removing a measured redundant theme through a focused doctor result or migrate its appearance to a non-executable definition. Exact adapters may later disable a known collector only when a pinned fixture proves that the operation is complete, reversible, and does not remove unrelated behavior.

## Reproduction

```sh
tests/zsh-config-coexistence.zsh target/release/wsh <bundle> present

benchmarks/probe-omz-coexistence.zsh benchmarks/zsh-config-coexistence-2026-09-03/ownership.tsv target/release/wsh <bundle> <omz-checkout> <wakamex-checkout> <autosuggestions-checkout> <syntax-highlighting-checkout>

benchmarks/benchmark-config-coexistence.zsh benchmarks/zsh-config-coexistence-2026-09-03/startup.tsv target/release/wsh <bundle> <omz-checkout> <wakamex-checkout> <autosuggestions-checkout> <syntax-highlighting-checkout>

benchmarks/summarize-config-startup.zsh benchmarks/zsh-config-coexistence-2026-09-03/startup.tsv benchmarks/zsh-config-coexistence-2026-09-03/startup-summary.tsv

benchmarks/trace-config-startup-processes.zsh benchmarks/zsh-config-coexistence-2026-09-03/startup-processes.tsv target/release/wsh <bundle>
```

Each source checkout must contain the revision recorded in `metadata.txt`; the harness archives the clean committed files and excludes working-tree modifications. The baseline result, raw startup samples, deterministic summary, and complete ownership rows are retained beside this report.
