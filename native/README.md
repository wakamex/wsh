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
