# Native Wsh release draft

This draft covers changes since v0.3.1 through `b12185f`. The release version and publication are pending.

Wsh starts directly as a native Zsh executable and installs as a system package. Account login no longer depends on a per-user active bundle record. Existing Zsh startup files, Oh My Zsh configuration, history, theme definitions and job control remain supported. ([Native startup](https://github.com/wakamex/wsh/commit/0f8bb8b), [package qualification](https://github.com/wakamex/wsh/commit/1064e43))

## Installation and command migration

The native distribution targets x86-64 Fedora RPM installations, with a glibc 2.28 build floor. Install, upgrade and downgrade the selected package with DNF. Migration from the per-user launcher requires installing the system package; `wsh update` does not perform this migration. A hosted DNF repository is not configured. Follow the [migration guide](https://github.com/wakamex/wsh/blob/b12185f/NATIVE-MIGRATION.md) to test `/usr/bin/wsh`, change an account shell, and handle an older launcher earlier in PATH without deleting configuration or history. ([Migration](https://github.com/wakamex/wsh/commit/e957101), [distribution tooling](https://github.com/wakamex/wsh/commit/4cb80d5))

Native Wsh preserves Zsh's command-line parsing. Wsh tools use explicit options:

| Previous command | Native command |
| --- | --- |
| `wsh version` | `wsh --wsh-version` |
| `wsh doctor` | `wsh --wsh-doctor` |
| `wsh profile` | `wsh --wsh-profile -- -i` |
| `wsh profile --functions` | `wsh --wsh-profile --functions -- -i` |
| `wsh profile report DIRECTORY` | `wsh --wsh-profile-report DIRECTORY` |
| `wsh -- PROGRAM ARG...` | `wsh --wsh-run -- PROGRAM ARG...` |
| `wsh run-foreground --login -- PROGRAM ARG...` | `wsh --wsh-run --login -- PROGRAM ARG...` |
| `wsh run -- ZSH_ARGUMENTS...` | `wsh ZSH_ARGUMENTS...` |
| `wsh update` / bundle rollback | DNF upgrade / downgrade of the selected native RPM |

`wsh --version` reports Zsh's version, and `--` keeps its normal Zsh meaning. Ordinary script names such as `doctor`, `profile`, `run` and `update` are no longer manager subcommands. `wsh --wsh-help` lists the native interface. ([Command boundaries](https://github.com/wakamex/wsh/commit/1abf1a9))

## Interactive improvements

- Main syntax highlighting runs in C while retaining styles, redraw integration and optional highlighters. Complete redraw medians fell by 35–91% across four installed benchmark workloads, with 287 upstream fixtures and 3,360 actual-style prefix comparisons passing. Recognized upstream copies also hand main parsing to Wsh. ([Installed results](https://github.com/wakamex/wsh/blob/b12185f/benchmarks/native-highlighting-installed-2026-09-10/report.md), [upstream takeover](https://github.com/wakamex/wsh/commit/1f9c258))
- Native autosuggestions preserve configured styles, custom strategies, widget behavior and asynchronous cancellation. Native history substring search preserves navigation and highlight composition. ([Autosuggestions](https://github.com/wakamex/wsh/commit/c78fbf4), [history](https://github.com/wakamex/wsh/commit/6f21a1b))
- Native `z` queries and persistence keep the existing database format and settings, including whole-database confirmation and bind-mounted database updates. Recognized upstream `z` copies use the native owner. ([Directory qualification](https://github.com/wakamex/wsh/commit/625c7f2), [takeover](https://github.com/wakamex/wsh/commit/7bbee20))
- The bundled `compinit` uses a native registration scanner. Cold completion startup p95 fell from 155.4 to 123.6 ms in the installed benchmark; first and second Tab stayed within the fixed 100 ms budgets. Existing initialization, security checks, caches and completion functions remain supported. ([Installed results](https://github.com/wakamex/wsh/blob/b12185f/benchmarks/native-adoption-2026-09-10/completion/report.md))
- Cataloged plugin copies and verified upstream Git checkouts can use Wsh's current native implementations while modified or unverified implementations remain external. New upstream features may temporarily be absent from the native implementation. Catalog matching remains the fast path; the tested uncataloged Git checkout added about 12 ms to median startup. ([Recognition policy and results](https://github.com/wakamex/wsh/blob/b12185f/benchmarks/git-provenance-2026-09-10/report.md))
- When `WSH_THEME` selects Wsh's prompt, Wsh removes recognized Oh My Zsh `git-prompt` collector hooks to avoid duplicate collection. ([Prompt ownership](https://github.com/wakamex/wsh/commit/9a5c703))
- Neutral syntax-highlight regions retain their ownership metadata so plugins can remove them on later redraws. ([Zsh fix](https://github.com/wakamex/wsh/commit/ab1691c))

## Native tools and packaging

Diagnostics, profiling and exact-argument foreground startup live in the native executable. The prompt uses one C helper per shell. The Rust manager, runtime crates and Rust toolchain dependency have been removed from the build. Profiling covers early exits and keeps child-shell tracing isolated; saved reports retain the documented migration path. ([Profiling](https://github.com/wakamex/wsh/commit/3f8b50d), [isolation](https://github.com/wakamex/wsh/commit/5205c70), [Rust retirement](https://github.com/wakamex/wsh/commit/32d2bc6))

Bundled Zsh modules stay linked to running shells across package replacement. Ordinary RPM removal refuses while a local account names `/usr/bin/wsh` or `/bin/wsh` as its shell. The release workflow compares two independently built RPMs and manifests and publishes GitHub build provenance. ([Module lifetime](https://github.com/wakamex/wsh/commit/aa4f0d2), [package contract](https://github.com/wakamex/wsh/blob/b12185f/RELEASES.md))

[Reviewed source range: v0.3.1 through b12185f](https://github.com/wakamex/wsh/compare/v0.3.1...b12185f)
