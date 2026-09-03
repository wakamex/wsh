# Existing Zsh configuration must load once without duplicate wsh ownership

The current bundle forces its own `ZDOTDIR`, so an ordinary `wsh` session does not load the user's `.zshrc`, aliases, Oh My Zsh setup, selected theme, or executable plugins. The first compatibility intervention must preserve existing startup behavior, install `wsh` integration afterward, and avoid claiming that a second prompt renderer, Git collector, lifecycle owner, or ZLE implementation is harmless.

The baseline and counterfactual use source revision `562773dc69962c88b87dd495d42f5b1a68f6675a`, development bundle `cdf7d443efdfac9d9f0c8a9aa8cc9778ef15f2a43666d734372c819a6d4ffa13`, bundled Zsh 5.9.2, Oh My Zsh commit `9112b53fa8b5ab556c7c893aa8be8a247ac512a0`, Wakamex commit `15c7c78214774408a6c007d0401415c7d0cded38`, zsh-autosuggestions commit `85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5`, and zsh-syntax-highlighting commit `2fc57d63067c18b1100ecdbf684fa5baf49459d1`. Clean files from those revisions supply the fixtures; unrelated local modifications are excluded.

## The smallest counterfactual preserves startup-file ownership

The launcher records the user-selected `ZDOTDIR`, or `HOME` when `ZDOTDIR` is unset, before selecting the bundle startup directory. Bundle-owned startup adapters invoke the corresponding existing user startup files once in native order, preserve changes to the user's effective `ZDOTDIR`, and load `wsh` integration after the interactive `.zshrc`. They do not parse, copy, convert, or rewrite startup source.

The first intervention does not suppress an existing theme or plugin. It records ownership and cost first. Automatic treatment is accepted later only for a case whose detection and treatment are deterministic, local, reversible, and proven by this harness. An unresolved overlap produces evidence for a focused doctor check rather than a guessed configuration edit.

## Correctness precedes timing

Fixtures cover an empty user directory, plain `.zshenv`, `.zprofile`, `.zshrc`, `.zlogin`, and `.zlogout` markers, a changed `ZDOTDIR`, Oh My Zsh without a theme, representative Oh My Zsh prompt paths, Wakamex, and the combined history-substring-search, zsh-autosuggestions, and zsh-syntax-highlighting plugins. Interactive non-login and login shells verify native startup order. A non-interactive shell verifies `.zshenv` without loading interactive integration.

The intervention passes correctness only when:

- Every applicable user startup file runs exactly once and in native order.
- User aliases, functions, options, completion functions, and unrelated hooks remain available.
- Existing `precmd` and `preexec` hooks retain their relative order and run once.
- `wsh` registers one runtime, one reader, one `precmd`, one `preexec`, and one `zshexit` hook even when its integration is sourced twice.
- The three ZLE plugins expose their advertised widgets together without protocol text, job announcements, status corruption, or a dead editor.
- The enabled presentation has one recorded owner, and the harness reports any legacy prompt, Git, or repaint machinery that remains active beside `wsh`.
- The existing runtime PTY suite continues to pass its Ctrl-C, command-status, directory-transition, asynchronous-refresh, and normal-exit lifecycle assertions through the managed configuration path.

## Performance identifies material overlap

Correct variants run 5 warmups followed by 20 forward and 20 reverse startup measurements on one pinned CPU. The harness compares plain configuration with direct `wsh` integration and through the managed launcher under the same instrumentation mode. The representative managed Oh My Zsh variants report child-process executions for one settled trivial prompt transition plus hook, prompt-owner, and widget state. Existing runtime repaint and memory gates remain covered by their dedicated retained experiments rather than being repeated for an unchanged runtime.

The startup adapter itself passes when its first-editable p90 overhead over the same user configuration plus direct integration is at most 1 ms and it starts no child process. Existing configuration cost is reported separately rather than charged to the adapter. A duplicate implementation is material when removing only that duplicate eliminates a child process, at least 1 ms at p90 from first-editable or settled latency, an extra repaint, or an observable correctness failure. These thresholds decide whether duplicate avoidance proceeds; they do not authorize suppressing arbitrary user code.

The hypothesis gets one startup-adapter implementation and one local correction, with a four-hour limit. A second failure requires revisiting the startup ownership model before adding a parser, migration framework, hook broker, or native module.
