# Native Wsh workbench

This directory contains the native implementation under development. Local builds are unsigned development artifacts. Published v0.3.1 remains on the legacy bundle path; the current source selects the native implementation and system-package workflow.

The native executable preserves Zsh argument handling. Wsh tools use an explicit option in the first argument position. An ordinary script called `doctor`, `profile`, `version`, `update`, or `run` remains a script. `--` remains Zsh's end-of-options marker.

| Native invocation | Purpose | Previous invocation |
|---|---|---|
| `wsh --wsh-version` | Detailed compiled Wsh and Zsh identity, without loading configuration | `wsh version` |
| `wsh --wsh-doctor` | Inspect an isolated interactive startup and report ownership findings | `wsh doctor` |
| `wsh --wsh-profile [--functions] -- <zsh arguments>` | Profile a shell | `wsh profile ...` |
| `wsh --wsh-profile-report <directory>` | Recover a saved profile | `wsh profile report ...` |
| `wsh --wsh-run [--login] -- <command> [arguments...]` | Run exact argv as a foreground job, then present an interactive shell | `wsh -- <argv>` or `wsh run-foreground ...` |
| `wsh --wsh-help` | Show the native Wsh interface | No equivalent |

`wsh --wsh-version` reports the compiled build label: `unsigned development artifact` for development builds or `release build` for release-mode builds. The label does not verify installed resources or authenticate release provenance. Runtime environment variables and mutable installation metadata do not change it.

`wsh --version` retains upstream Zsh's version output. Native options cannot be mixed into the middle of Zsh arguments; use the profile command's explicit separator or the foreground command's `--login` option. Arguments after a script name, `-c` command, or `--` are never reinterpreted as Wsh tools.

Installation and updates belong to the system package manager. There is no native activation-state or self-update command. The [tested migration](../NATIVE-MIGRATION.md) preserves access to the old manager for published bundles and exceptional saved reports. Help lists the implemented native tools.

Build the selected native path with `./build/build-native-installation.zsh`. The separate native source lock pins the C additions and startup patch, and the builder rejects stale locks or cached outputs with a different compiled identity. Run the resulting `bundles/<identity>/bin/wsh` directly. The native payload contains the tested C helper, its parser licenses and the effective native source/module configuration. The assembler uses the Python native inventory verifier and retains a private `bin/zsh` for compatibility tests. Rust crates and toolchain requirements have been removed. It does not install the legacy startup-redirection directory.

Native startup preserves ordinary Zsh file order, execution context, status, and ZDOTDIR behavior. Resource relocation also works under `-f`. Successfully loaded Wsh defaults suppress the automatic upstream new-user wizard, and no user startup files are created. Optional integration or runtime failures leave basic shell startup available. The [retained tests and measurements](../benchmarks/native-build-2026-09-08/report.md) establish local behavior; [final system-package login qualification](../benchmarks/native-qualification-2026-09-09/package-report.md) also passes.

Native builds link the configured bundled Zsh modules into the executable while preserving dynamic loading for external modules. A running shell keeps its bundled module code after package replacement. [The comparison](../benchmarks/native-qualification-2026-09-09/modules-report.md) passes startup, memory, upstream and external-module checks. Installation-relative function lookup also [removes stale build-directory fallbacks](../benchmarks/native-qualification-2026-09-09/paths-report.md) while preserving explicitly exported `FPATH`.

Native profiling is available with `bin/wsh --wsh-profile -- -i`, optionally adding `--functions` before the separator. Exit normally for a report, or recover a saved directory with `bin/wsh --wsh-profile-report <directory>`. The native build now requires Jansson development headers and its system shared library. [Invocation and report tests](../benchmarks/native-profile-2026-09-08/report.md), native startup recovery, and [child isolation](../benchmarks/native-profile-isolation-2026-09-08/report.md) pass. Function tables describe initialization through the first editable prompt. [Local package/floor qualification](../benchmarks/native-qualification-2026-09-09/floor-report.md) passes; publication decisions are retained.
