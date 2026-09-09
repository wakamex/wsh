# wsh

`wsh` is a fast, tested Zsh distribution with the everyday conveniences people install Oh My Zsh for, while remaining compatible with existing `.zshrc` files and Oh My Zsh setups.

- Keep your `.zshrc`, Oh My Zsh setup, and familiar Zsh commands.
- Type less with autosuggestions and history substring search, and spot mistakes with syntax highlighting built in.
- Jump back to frequently used directories with `z`.
- Keep your existing prompt or choose Minimal, Wakamex, Robbyrussell, or Agnoster with asynchronous Git updates.
- Find startup slowdowns with `wsh profile` and redundant plugin setup with `wsh doctor`.
- Update explicitly and roll back offline if needed.
- Navigate prompts and command output in compatible terminals.

These features are included in v0.3.1.

## Motivation

Zsh is a capable shell, but building a polished interactive environment usually means assembling a framework, themes, plugins, completion files, and terminal integration. Those pieces often own overlapping machinery for Git state, hooks, caching, background work, and prompt repainting. Choosing a visual theme can therefore also choose its performance and correctness behavior.

The [`zsh-theme-bench` benchmark](https://github.com/wakamex/zsh-theme-bench/blob/main/research/core-theme-benchmark-2026-09-02.md) ran representative prompt architectures in fresh interactive terminals against the same 1,000-file Git fixture. The tested paths ranged from one optional-lock-safe background Git scan to 16 synchronous Git calls per transition, with corresponding differences in prompt latency and state correctness. The detailed evidence and scope are recorded in [MOTIVATION.md](MOTIVATION.md).

`wsh` separates presentation from state collection. A theme definition selects trusted prompt components and declares the structured fields it needs without executing shell code. Shared providers own external commands, asynchronous work, cache invalidation, cancellation, freshness, and publication. Fixing a provider can then improve every theme that uses it.

## What wsh aims to provide

- Fish-like interactive usability while retaining existing `.zshrc` files, Oh My Zsh setups, shell commands, Zsh scripts, completion functions, and executable plugins
- Shared structured state providers, beginning with Git prompt state
- Non-executable theme definitions and an open-submission directory governed by mechanical safety and resource checks rather than stylistic approval
- Fast editable prompts, bounded asynchronous refresh, and composed repainting
- Exact foreground application startup with native Zsh job control and one prompt afterward
- Immutable bundles that pair one exact Zsh build with its tested Wsh runtime
- Explicit, signed, reproducible, atomic, and reversible updates with no update work during shell startup
- Built-in profiling and tracing for startup, prompts, providers, child processes, and repaints
- Reproducible correctness fixtures and benchmarks for performance claims and new feature decisions

## Install

The supported target is x86-64 Linux with glibc 2.28 or newer. Install the current immutable GitHub Release:

```sh
curl --proto '=https' --tlsv1.2 -fsSL https://github.com/wakamex/wsh/releases/latest/download/wsh-install.sh | sh
```

Then start Wsh with `wsh`. The explicit `wsh run` form accepts Zsh arguments after `--`, such as `wsh run -- -f`. The installer uses `~/.local/bin`; add that directory to `PATH` or run `~/.local/bin/wsh` directly if necessary.

Keep system Bash or Zsh as your account login shell and start Wsh from your terminal. Do not set the per-user Wsh launcher as your login shell with `chsh`: it depends on per-user bundle state and an executable in your home directory. A failure there can prevent graphical and TTY login. [Login-shell recovery and limitations](LOGIN.md) describes the development recovery path and the remaining boundaries.

A separate [native system-package migration](NATIVE-MIGRATION.md) is being qualified locally. It starts Zsh without private activation state and uses the system package manager for updates. The published installation above remains the legacy distribution.

Use `wsh update --check` to check without changing anything, `wsh update` to install a newer current release, or `wsh update --to vX.Y.Z` to select an exact version. `wsh bundle rollback` returns to the previously active verified bundle without a network request.

`wsh --version` reports the installed launcher version. `wsh version` also reports the active bundle's release or development identity, Wsh source revision, bundled Zsh version and source revision, target, and bundle digest.

Run `wsh profile` to start a normal interactive session that reports launcher, startup-file, built-in, provider, rendering, and first-editor timing when you exit. `wsh profile --functions` adds Zsh function-level timing. [PROFILING.md](PROFILING.md) defines the captured data, privacy limits, and recovery command.

## Directory jumping

Wsh supplies `z` when your configuration has not already defined a directory-jump command. Visit a directory, then use part of its name to return:

```sh
cd /code/my-project
cd /tmp
z my-project
```

The pinned Zsh-z implementation ranks visited directories by frequency and recency and persists them in `~/.z`. It uses the same data format and `ZSHZ_*` settings as OMZ's `z` plugin, including `ZSHZ_DATA` for another database path and `ZSHZ_CMD` for another command name. Existing OMZ, zoxide, and custom command definitions remain in charge. Set `WSH_DISABLE_DIRECTORY_JUMP=1` in `.zshrc` to disable Wsh's default. Tab completion uses your existing Zsh completion setup; Wsh does not initialize a new completion framework.

## Prompt selection

Wsh preserves your existing prompt when `WSH_THEME` is unset or empty. Select a Wsh theme to enable its prompt and asynchronous Git collector:

```sh
WSH_THEME=wakamex wsh
WSH_THEME=minimal wsh
WSH_THEME=robbyrussell wsh
WSH_THEME=agnoster wsh
WSH_THEME=/path/to/theme.toml wsh
```

These are terminal commands. All four bundled names and explicit theme-definition paths are supported. [THEMES.md](THEMES.md) describes the ports and the strict format. Wsh's editing features remain enabled with or without its prompt.

In a shared `.zshrc`, put this after your existing `ZSH_THEME` assignment and before sourcing `oh-my-zsh.sh`:

```zsh
if [[ -n ${WSH_THEME-} ]]; then
  ZSH_THEME=""
fi
```

Regular Zsh continues to load your OMZ theme when `WSH_THEME` is unset. Wsh keeps the theme selection local to its session so nested regular Zsh does not inherit it. Avoid unconditionally assigning or globally exporting `WSH_THEME` in a shared configuration: that would also select it for regular Zsh and trigger the conditional there. Selection takes effect after `.zshrc`; changing it later does not switch an active renderer. If the selected definition is missing or invalid, Wsh reports the failure and leaves the prompt from user startup in place.

`WSH_THEME=wakamex wsh doctor` checks the same startup choice. If OMZ still has a theme configured alongside Wsh's prompt, doctor suggests the conditional above or clearing `WSH_THEME`. Theme selection alone does not stop OMZ from loading its theme. Doctor never edits startup files or unloads arbitrary theme hooks. Further cleanup follows identified duplication; retain conditional declarations for plugins you still use in regular Zsh.

## Current status

The bundled Zsh build incorporates 1,074 upstream master commits since Zsh 5.9 ([upstream NEWS](https://github.com/zsh-users/zsh/blob/cad0d67c76e2be7371cf3526b79ea2581810d35a/NEWS), [Wsh validation](benchmarks/edge-zsh-2026-09-03/report.md)).

It also includes two Wsh-maintained Zsh source patches:

- Terminal reporting fixes produce valid OSC 133 prompt identifiers and restore the shell's OSC 7 working directory after foreground applications change the terminal's reported directory, including when the optional terminal query is disabled. See the [terminal integration tests and results](benchmarks/native-terminal-integration-2026-09-04/report.md).
- The `zcompile` fix zeroes uninitialized alignment padding in compiled functions, making bundle builds reproducible and preventing those bytes from containing stale heap data. See the [reproducibility tests and results](benchmarks/zcompile-reproducibility-2026-09-04/report.md).

Both patches are included in the [pinned Zsh source definition](build/zsh-sources/zsh-cad0d67c.json) and passed the upstream Zsh and Wsh test suites. The [architecture evidence record](ARCHITECTURE-EVIDENCE.md) tracks these native fixes alongside launcher and startup integration findings.

The current source includes native loading of existing Zsh configuration, the three interactive defaults above, a focused `wsh doctor` command for exact redundant plugin declarations, end-to-end shell profiling, structured foreground application startup, native OSC 7 and OSC 133 terminal integration, the shared asynchronous Git provider, four data-only theme presentations, verified installation, explicit updates, offline rollback, and a pinned post-5.9 Zsh revision that passed the complete Wsh correctness and performance gates. Doctor reports modified or unrecognized implementations without replacing them and never edits startup files. Development builds remain unsigned local artifacts until a tagged release passes the complete compatibility, correctness, performance, reproducibility, and provenance gates. The public theme directory is not implemented yet.

Terminal integration currently covers OSC 7 working-directory reports and the OSC 133 `A`, `B`, `C`, and `D` prompt and output boundaries. Exit status, progress, and broader foreground-job transitions remain evidence-gated. [TERMINAL-INTEGRATION.md](TERMINAL-INTEGRATION.md) defines the exact sequences, ownership, and tested behavior.

## Planned capabilities require evidence

Current investigations include application-backed dynamic completion, stable pane identity with bounded pane-local and private history, terminal compatibility diagnostics, and allowlisted terminal metadata. A separate foreground-job event protocol is deferred because Wakterm's owner-local process-identity fix passes the current lifecycle reproducer.

Each candidate begins with a reproducible current weakness, the cheapest owner-local counterfactual, and a measurable consumer improvement. A new daemon, database, protocol, or compatibility layer is not accepted solely because it is architecturally attractive. [FEATURES.md](FEATURES.md) records the admission rules, evidence, priorities, and deferred ideas.

## What wsh is not

`wsh` does not replace the Zsh language, parser, job-control engine, or ZLE line editor. It is not a new shell language, an Oh My Zsh fork, a sandbox for arbitrary Zsh configuration, a promise to support every executable plugin, a terminal emulator, a multiplexer, or a generic daemon for every kind of shell state.

Zsh remains the shell engine. Applications remain authoritative for their command models and state. Terminals remain responsible for panes, rendering, scrollback, focus, and input encoding. `wsh` owns only the distribution, shared services, integrations, and measurements that pass its evidence gates.

## Documentation

- [MOTIVATION.md](MOTIVATION.md) explains the benchmark evidence and product direction.
- [DESIGN.md](DESIGN.md) defines the provider, renderer, theme, runtime, and distribution contracts.
- [IMPLEMENTATION.md](IMPLEMENTATION.md) records the current implementation, accepted results, target, bundle format, and performance gates.
- [PROFILING.md](PROFILING.md) defines the user-facing profile command, report, captured spans, privacy limits, and retained evidence.
- [DEVELOPMENT.md](DEVELOPMENT.md) defines the local workflow, CI, testing, benchmarking, and evidence-retention rules.
- [FEATURES.md](FEATURES.md) ranks later investigations and links their detailed experiment specifications.
- [SECURITY.md](SECURITY.md) and [RELEASES.md](RELEASES.md) define theme authority, official artifacts, reproducibility, attestations, activation, and rollback.
- [VENDORED-COMPONENTS.md](VENDORED-COMPONENTS.md) records exact third-party snapshots and Wsh's behavior around them.

## License

Original `wsh` work is available under the [MIT License](LICENSE). Bundled or adapted third-party components retain their own licenses and notices.
