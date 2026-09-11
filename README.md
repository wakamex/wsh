# wsh

`wsh` is a fast, tested Zsh distribution with autosuggestions, history search, syntax highlighting and directory jumping built in. Keep your existing `.zshrc`, Oh My Zsh setup and familiar Zsh commands.

This README describes the native RPM distribution under development. Published v0.3.1 uses the earlier per-user launcher; see its [installation instructions](https://github.com/wakamex/wsh/blob/v0.3.1/README.md) or the [native migration guide](NATIVE-MIGRATION.md).

- Type less with autosuggestions and history substring search, and spot mistakes with syntax highlighting built in.
- Use native implementations of recognized upstream plugins while keeping their supported settings; custom and unverified plugins keep running externally.
- Jump back to frequently used directories with `z`.
- Keep your existing prompt or choose Minimal, Wakamex, Robbyrussell, or Agnoster with asynchronous Git updates.
- Find startup slowdowns with `wsh --wsh-profile -- -i` and redundant plugin setup with `wsh --wsh-doctor`.
- Use a system-owned login shell that starts without per-user bundle state, with installation, upgrades and downgrades managed through DNF.
- Navigate prompts and command output in compatible terminals.

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
- System packages that pair one exact Zsh build with its tested Wsh runtime
- Reproducible packages with explicit system-managed updates and no update work during shell startup
- Built-in profiling and tracing for startup, prompts, providers, child processes, and repaints
- Reproducible correctness fixtures and benchmarks for performance claims and new feature decisions

## Install

The native distribution targets x86-64 Fedora RPM installations, built against glibc 2.28. Native packages have not been published yet. Build instructions are in [DEVELOPMENT.md](DEVELOPMENT.md); local artifacts are unsigned development builds.

Once you have a selected native RPM, replace the placeholder filename below with its actual name and test it in an isolated machine with an independent recovery account:

```sh
sudo dnf install ./wsh-VERSION-RELEASE.x86_64.rpm
/usr/bin/wsh --wsh-version
/usr/bin/wsh -l
```

The absolute path selects the native package even when an older `~/.local/bin/wsh` is earlier in PATH. After testing your configuration, use `chsh -s /usr/bin/wsh` if you want it as your login shell. Keep the existing session open until a separate login succeeds. Follow the [migration guide](NATIVE-MIGRATION.md) before retiring the old launcher.

Install upgrades and downgrades explicitly through DNF using the selected RPM. There is no hosted DNF repository yet, and the legacy `wsh update` command does not migrate to the native distribution.

Published v0.3.1 installation instructions remain available in its [versioned README](https://github.com/wakamex/wsh/blob/v0.3.1/README.md). Keep a system shell as the account shell when using that per-user launcher: missing activation state or an unavailable home executable can prevent login. Native package installation replaces that dependency with a system-owned executable.

Native Wsh preserves Zsh command-line parsing. Run `wsh` normally, `wsh --wsh-doctor` for diagnostics, `wsh --wsh-version` for distribution identity and `wsh --wsh-profile -- -i` for an interactive profile. `wsh --wsh-run -- PROGRAM ARG...` starts an exact foreground command with native job control and returns to the prompt. See [PROFILING.md](PROFILING.md) for profiling and recovery.

## Directory jumping

Wsh supplies `z` when your configuration has not already defined a directory-jump command. Visit a directory, then use part of its name to return:

```sh
cd /code/my-project
cd /tmp
z my-project
```

The native directory implementation ranks visited directories by frequency and recency, persisting them in `~/.z`. It uses the same data format and `ZSHZ_*` settings as OMZ's `z` plugin, including `ZSHZ_DATA` for another database path and `ZSHZ_CMD` for another command name. Recognized unmodified OMZ `z` copies use the native implementation with their existing data and settings. Zoxide and custom or unverified implementations remain in charge. Set `WSH_DISABLE_DIRECTORY_JUMP=1` in `.zshrc` to disable Wsh's default. Tab completion uses your existing Zsh completion setup; Wsh does not initialize a new completion framework.

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

`WSH_THEME=wakamex wsh --wsh-doctor` checks the same startup choice. If OMZ still has a theme configured alongside Wsh's prompt, doctor suggests the conditional above or clearing `WSH_THEME`. Theme selection alone does not stop OMZ from loading its theme. Doctor never edits startup files or unloads arbitrary theme hooks. Further cleanup follows identified duplication; retain conditional declarations for plugins you still use in regular Zsh.

## Current status

Two independent canonical release-mode builds produced identical RPMs and installation manifests. The selected package passed fresh Fedora QEMU installation, real PAM login, job control, legacy migration, optional-resource recovery and reboot with SELinux enforcing; see the [qualification report](benchmarks/release-qualification-2026-09-10/report.md). These remain unsigned local artifacts pending an authorized release.

The bundled Zsh build incorporates 1,074 upstream master commits since Zsh 5.9 ([upstream NEWS](https://github.com/zsh-users/zsh/blob/cad0d67c76e2be7371cf3526b79ea2581810d35a/NEWS), [Wsh validation](benchmarks/edge-zsh-2026-09-03/report.md)).

The bundled Zsh carries Wsh-maintained correctness fixes:

- Terminal reporting fixes produce valid OSC 133 prompt identifiers and restore the shell's OSC 7 working directory after foreground applications change the terminal's reported directory, including when the optional terminal query is disabled. See the [terminal integration tests and results](benchmarks/native-terminal-integration-2026-09-04/report.md).
- The `zcompile` fix zeroes uninitialized alignment padding in compiled functions, making bundle builds reproducible and preventing those bytes from containing stale heap data. See the [reproducibility tests and results](benchmarks/zcompile-reproducibility-2026-09-04/report.md).
- Neutral syntax-highlight regions retain their ownership markers, so plugins can remove them on subsequent redraws instead of accumulating stale regions. See the [Zsh upstream candidate and reproducer](UPSTREAM-ZSH-BUGS.md#neutral-highlight-attributes-discard-ownership-metadata).

These fixes are included in the [pinned Zsh source definition](build/zsh-sources/zsh-cad0d67c.json) and passed the upstream Zsh and Wsh test suites. The [native source definition](build/zsh-sources/zsh-cad0d67c-native.json) additionally selects native startup, completion scanning and the C interactive components. Wsh-owned main syntax highlighting parses each redraw in C while preserving upstream styles and optional highlighters; see the [installed comparison](benchmarks/native-highlighting-installed-2026-09-10/report.md). The [architecture evidence record](ARCHITECTURE-EVIDENCE.md) tracks these native fixes alongside launcher and startup integration findings.

The current source includes native loading of existing Zsh configuration, the three interactive defaults above, native diagnostics for exact redundant plugin declarations, end-to-end shell profiling, structured foreground application startup, native OSC 7 and OSC 133 terminal integration, the shared asynchronous Git provider, four data-only theme presentations, verified native package assembly and system-managed updates, and a pinned post-5.9 Zsh revision that passed the complete Wsh correctness and performance gates. Recognized upstream `z` copies use native directory queries and persistence while keeping their existing database and configuration. When Wsh owns the prompt, it also deactivates the recognized Oh My Zsh `git-prompt` collector hooks. Recognized upstream syntax-highlighting copies, including the tested older `0.8.0-alpha2-dev` revision, use Wsh’s native main parser while retaining styles and additional highlighters. Doctor reports modified or unrecognized implementations without replacing them and never edits startup files. Development builds remain unsigned local artifacts until a tagged release passes the complete compatibility, correctness, performance, reproducibility, and provenance gates. The public theme directory is not implemented yet.

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
- [SECURITY.md](SECURITY.md) and [RELEASES.md](RELEASES.md) define theme authority, official artifacts, reproducibility, attestations and package-managed updates.
- [VENDORED-COMPONENTS.md](VENDORED-COMPONENTS.md) records exact third-party snapshots and Wsh's behavior around them.

## License

Original `wsh` work is available under the [MIT License](LICENSE). Bundled or adapted third-party components retain their own licenses and notices.
