# Native Wsh release draft

This draft covers changes since v0.3.1 through `37ed977`. The release version and publication are pending.

Wsh starts directly as a native Zsh executable and installs as a system package. Account login no longer depends on a per-user active bundle record. Existing Zsh startup files, Oh My Zsh configuration, history, theme definitions and job control remain supported. ([Native startup](https://github.com/wakamex/wsh/commit/0f8bb8b), [package qualification](https://github.com/wakamex/wsh/commit/1064e43))

## Installation and commands

The distribution targets x86-64 Fedora RPM installations, with a glibc 2.28 build floor. Install, upgrade and downgrade the selected package with DNF. A hosted DNF repository is not configured. Test `/usr/bin/wsh -l` before selecting `/usr/bin/wsh` as your account shell. ([Package qualification](https://github.com/wakamex/wsh/commit/ddb3efc), [distribution tooling](https://github.com/wakamex/wsh/commit/4cb80d5))

Wsh preserves Zsh's command-line parsing and provides explicit tool options:

| Task | Command |
| --- | --- |
| Distribution identity | `wsh --wsh-version` |
| Diagnostics | `wsh --wsh-doctor` |
| Interactive profile | `wsh --wsh-profile -- -i` |
| Function-level profile | `wsh --wsh-profile --functions -- -i` |
| Saved profile report | `wsh --wsh-profile-report DIRECTORY` |
| Foreground application, then prompt | `wsh --wsh-run -- PROGRAM ARG...` |

`wsh --version` reports Zsh's version, and `--` keeps its normal Zsh meaning. `wsh --wsh-help` lists the native tools. ([Command boundaries](https://github.com/wakamex/wsh/commit/1abf1a9))

## Interactive improvements

- Main syntax highlighting runs in C while retaining styles, redraw integration and optional highlighters. Complete redraw medians fell by 35–91% across four installed benchmark workloads, with 287 upstream fixtures and 3,360 actual-style prefix comparisons passing. Recognized upstream copies also hand main parsing to Wsh. ([Installed results](https://github.com/wakamex/wsh/blob/b12185f/benchmarks/native-highlighting-installed-2026-09-10/report.md), [upstream takeover](https://github.com/wakamex/wsh/commit/1f9c258))
- Native autosuggestions reduce the complete 10,000-entry editing-sequence median from 7.294 to 5.160 ms (29.3%) and first-editable startup by about 6.6 ms in both tested prompt modes. Native history substring search reduces the 10,000-entry editing median from 11.032 to 8.526 ms in default mode (22.7%), and from 238.097 to 65.840 ms with uniqueness enabled (72.3%). Configured styles, strategies, navigation and editor composition remain supported. ([Autosuggestions](https://github.com/wakamex/wsh/commit/c78fbf4), [history](https://github.com/wakamex/wsh/commit/6f21a1b))
- Native `z` reduces complete 1,000-record lookup median from 52.542 to 8.540 ms (83.7%) and write median from 52.233 to 8.387 ms (83.9%). The existing database format and settings, whole-database confirmation and bind-mounted updates remain supported. Recognized upstream `z` copies use the native owner. ([Directory qualification](https://github.com/wakamex/wsh/commit/625c7f2), [takeover](https://github.com/wakamex/wsh/commit/7bbee20))
- The bundled `compinit` uses a native registration scanner. Cold completion startup p95 fell from 155.4 to 123.6 ms in the installed benchmark; first and second Tab stayed within the fixed 100 ms budgets. Existing initialization, security checks, caches and completion functions remain supported. ([Installed results](https://github.com/wakamex/wsh/blob/b12185f/benchmarks/native-adoption-2026-09-10/completion/report.md))
- Cataloged plugin copies and verified upstream Git checkouts can use Wsh's current native implementations while modified or unverified implementations remain external. New upstream features may temporarily be absent from the native implementation. Catalog matching remains the fast path; the tested uncataloged Git checkout added about 12 ms to median startup. ([Recognition policy and results](https://github.com/wakamex/wsh/blob/b12185f/benchmarks/git-provenance-2026-09-10/report.md))
- When `WSH_THEME` selects Wsh's prompt, Wsh removes recognized Oh My Zsh `git-prompt` collector hooks to avoid duplicate collection. ([Prompt ownership](https://github.com/wakamex/wsh/commit/9a5c703))
- Neutral syntax-highlight regions retain their ownership metadata so plugins can remove them on later redraws. ([Zsh fix](https://github.com/wakamex/wsh/commit/ab1691c))

## Native tools and packaging

Diagnostics, profiling and exact-argument foreground startup live in the native executable. The prompt uses one C helper per shell. The Rust manager, runtime crates and Rust toolchain dependency have been removed from the build. Profiling covers early exits and keeps child-shell tracing isolated. ([Profiling](https://github.com/wakamex/wsh/commit/3f8b50d), [isolation](https://github.com/wakamex/wsh/commit/5205c70), [Rust retirement](https://github.com/wakamex/wsh/commit/32d2bc6))

The complete C-versus-Rust helper comparison reduced executable size from 1,679,240 to 372,320 bytes (about 78%) and active collection threads from three to two. It passed the fixed latency gates, with largest paired p95 increases of 0.207 ms for Git collection and 0.419 ms for startup. The isolated Git/renderer ports did not establish useful latency improvements; their benefit came from consolidating the complete helper. ([Measured comparison](https://github.com/wakamex/wsh/blob/b12185f/benchmarks/native-render-2026-09-08/runtime-report.md), [C helper](https://github.com/wakamex/wsh/commit/412798d))

The editing, directory and completion results above compare native C implementations with their pinned Zsh-script counterparts, using 50 alternating pairs per workload. The helper result compares C with Rust. These component results come from separate qualified revisions and are not additive or a final-release-wide speedup claim.

Bundled Zsh modules stay linked to running shells across package replacement. Ordinary RPM removal refuses while a local account names `/usr/bin/wsh` or `/bin/wsh` as its shell. The release workflow compares two independently built RPMs and manifests and publishes GitHub build provenance. ([Module lifetime](https://github.com/wakamex/wsh/commit/aa4f0d2), [package contract](https://github.com/wakamex/wsh/blob/b12185f/RELEASES.md))

[Source range: v0.3.1 through 37ed977](https://github.com/wakamex/wsh/compare/v0.3.1...37ed977)
