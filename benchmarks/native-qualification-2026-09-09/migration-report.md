# Migration preserves user files and native foreground arguments

A private fixture verifies that an earlier per-user launcher remains selected by PATH, the absolute native executable works despite corrupt legacy state, retiring only the old command name exposes native Wsh after `rehash`, and the explicitly renamed legacy manager remains usable. Configuration, history, local theme, activation state and legacy executable bytes remain unchanged. Native `doctor`, `profile`, `version`, `update` and `run` script names retain ordinary Zsh semantics.

Wakterm commit `e33307f0b` changes the actual restore caller for `/usr/bin/wsh` and `/bin/wsh` to native `--wsh-run --login --` invocation. Its three real CommandBuilder tests pass, including non-UTF-8 argument bytes and the retained legacy path. The selected Wsh installation's real foreground PTY suite passes separately. This verifies the caller and shell boundary; a complete graphical Wakterm restore was not exercised.

[NATIVE-MIGRATION.md](../../NATIVE-MIGRATION.md) provides the command mapping, PATH/account ordering, preservation and package recovery procedure. All execution used private fixtures or the disposable VM. No live host account shell or user dotfile changed. The Wakterm commit and Wsh commits remain local.
