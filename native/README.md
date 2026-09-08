# Native Wsh workbench

This directory contains the native implementation under development. Local builds are unsigned development artifacts. Production remains on the existing bundle path until the startup, packaging, and migration gates pass.

The native executable preserves Zsh argument handling. Wsh tools use an explicit option in the first argument position. An ordinary script called `doctor`, `profile`, `version`, `update`, or `run` remains a script. `--` remains Zsh's end-of-options marker.

| Native invocation | Purpose | Previous invocation |
|---|---|---|
| `wsh --wsh-version` | Detailed compiled Wsh and Zsh identity, without loading configuration | `wsh version` |
| `wsh --wsh-doctor` | Inspect an isolated interactive startup and report ownership findings | `wsh doctor` |
| `wsh --wsh-profile [--functions] -- <zsh arguments>` | Profile a shell | `wsh profile ...` |
| `wsh --wsh-profile-report <directory>` | Recover a saved profile | `wsh profile report ...` |
| `wsh --wsh-run [--login] -- <command> [arguments...]` | Run exact argv as a foreground job, then present an interactive shell | `wsh -- <argv>` or `wsh run-foreground ...` |
| `wsh --wsh-help` | Show the native Wsh interface | No equivalent |

`wsh --version` retains upstream Zsh's version output. Native options cannot be mixed into the middle of Zsh arguments; use the profile command's explicit separator or the foreground command's `--login` option. Arguments after a script name, `-c` command, or `--` are never reinterpreted as Wsh tools.

Installation and updates belong to the system package manager. There is no native activation-state or self-update command. Existing installations keep their old manager until migration has been tested. Each option becomes available as its stage is implemented; help lists only implemented tools.

Build the selected native path with `./build/build-native-installation.zsh`. The separate native source lock pins the C additions and startup patch, and the builder rejects stale locks or cached outputs with a different compiled identity. Run the resulting `bundles/<identity>/bin/wsh` directly. This development payload uses the existing assembler and still contains the Rust runtime and a duplicate `bin/zsh`; it does not install the legacy startup-redirection directory.

Native startup preserves ordinary Zsh file order, execution context, status, and ZDOTDIR behavior. Resource relocation also works under `-f`. Successfully loaded Wsh defaults suppress the automatic upstream new-user wizard, and no user startup files are created. Optional integration or runtime failures leave basic shell startup available. The [retained tests and measurements](../benchmarks/native-build-2026-09-08/report.md) establish local behavior; system-package login qualification is a separate stage.
