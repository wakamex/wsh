# wsh

`wsh` is a fast, tested Zsh distribution with the everyday conveniences people install Oh My Zsh for, while remaining compatible with existing `.zshrc` files and Oh My Zsh setups.

Currently includes:

- [`zsh-history-substring-search`](https://github.com/zsh-users/zsh-history-substring-search)
- [`zsh-autosuggestions`](https://github.com/zsh-users/zsh-autosuggestions)
- [`zsh-syntax-highlighting`](https://github.com/zsh-users/zsh-syntax-highlighting)
- Native prompt navigation, output zones, and working-directory reporting for compatible terminals
- A tested, pinned post-5.9 Zsh build incorporating 1,074 upstream master commits since Zsh 5.9 ([upstream NEWS](https://github.com/zsh-users/zsh/blob/cad0d67c76e2be7371cf3526b79ea2581810d35a/NEWS), [Wsh validation](benchmarks/edge-zsh-2026-09-03/report.md))

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
- Built-in profiling and tracing for startup, prompts, providers, child processes, repaints, completion, history, and terminal events
- Reproducible correctness fixtures and benchmarks for performance claims and new feature decisions

## Install

The supported target is x86-64 Linux with glibc 2.28 or newer. Install the current immutable GitHub Release:

```sh
curl --proto '=https' --tlsv1.2 -fsSL https://github.com/wakamex/wsh/releases/download/v0.1.3/wsh-v0.1.3-install.sh | sh
```

Then start Wsh with `wsh`. The explicit `wsh run` form accepts Zsh arguments after `--`, such as `wsh run -- -f`. The installer uses `~/.local/bin`; add that directory to `PATH` or run `~/.local/bin/wsh` directly if necessary.

Use `wsh update --check` to check without changing anything, `wsh update` to install a newer current release, or `wsh update --to vX.Y.Z` to select an exact version. `wsh bundle rollback` returns to the previously active verified bundle without a network request.

## Current status

`v0.1.3` is the current official release. It includes the bundled Zsh 5.9.2 runtime, shared asynchronous Git provider, two data-only theme presentations, verified installation, explicit updates, and offline rollback. Current development adds native loading of existing Zsh configuration, the three interactive defaults above, a focused `wsh doctor` command for exact redundant plugin declarations, structured foreground application startup, native OSC 7 and OSC 133 terminal integration, and a pinned post-5.9 Zsh revision that passed the complete Wsh correctness and performance gates. Doctor reports modified or unrecognized implementations without replacing them and never edits startup files. Development builds remain unsigned local artifacts until a tagged release passes the complete compatibility, correctness, performance, reproducibility, and provenance gates. The public theme directory is not implemented yet.

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
- [DEVELOPMENT.md](DEVELOPMENT.md) defines the local workflow, CI, testing, benchmarking, and evidence-retention rules.
- [FEATURES.md](FEATURES.md) ranks later investigations and links their detailed experiment specifications.
- [SECURITY.md](SECURITY.md) and [RELEASES.md](RELEASES.md) define theme authority, official artifacts, reproducibility, attestations, activation, and rollback.
- [VENDORED-COMPONENTS.md](VENDORED-COMPONENTS.md) records exact third-party snapshots and Wsh's behavior around them.

## License

Original `wsh` work is available under the [MIT License](LICENSE). Bundled or adapted third-party components retain their own licenses and notices.
