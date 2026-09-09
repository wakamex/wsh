# Native package migration

The native development package starts the bundled Zsh directly and uses the C helper for optional prompt work. Login no longer reads per-user activation records. The package owns `/usr/bin/wsh`, its `/bin/wsh` alias on Fedora, and resources under `/usr/libexec/wsh`. These instructions describe the tested local RPM prototype. Published Wsh releases still use the legacy bundle installer and updater.

## Preserve access while changing installations

Install the complete native RPM with DNF in a test machine with an independent working recovery account. Test `/usr/bin/wsh --wsh-version`, `/usr/bin/wsh --wsh-doctor`, and `/usr/bin/wsh -l` through the absolute path before selecting it as an account shell. Test the account's configuration and terminal behavior, then use `chsh -s /usr/bin/wsh`. Keep the existing login session open until a separate login succeeds. The package registers its supported paths in `/etc/shells`.

An earlier `~/.local/bin/wsh` in PATH still selects the legacy launcher. After the system installation and account login work, rename that one executable to `~/.local/bin/wsh-legacy`, then run `rehash` in existing Zsh sessions. `whence -p wsh` should resolve to the system installation. Keep the explicitly named legacy executable while old saved profiles or bundle rollback remain useful. The [private migration regression](native/test-migration.py) exercises this sequence against real executables and verifies that configuration, history, themes and activation state remain unchanged.

Do not remove the old executable while the account shell still names it. Change the account shell first. Native Wsh ignores legacy activation records, so those files do not need to be deleted or converted. Keep `.zshenv`, `.zprofile`, `.zshrc`, `.zlogin`, history and theme definitions. Existing `WSH_THEME` selection and regular Zsh coexistence continue to work. OMZ can remain loaded; doctor reports actionable duplicate ownership and prompt advice.

## Command migration

| Legacy command | Native package command |
|---|---|
| `wsh` | `wsh` |
| `wsh version` | `wsh --wsh-version` |
| `wsh doctor` | `wsh --wsh-doctor` |
| `wsh profile` | `wsh --wsh-profile -- -i` |
| `wsh profile --functions` | `wsh --wsh-profile --functions -- -i` |
| `wsh profile report DIRECTORY` | `wsh --wsh-profile-report DIRECTORY` |
| `wsh -- PROGRAM ARG...` | `wsh --wsh-run -- PROGRAM ARG...` |
| `wsh run-foreground --login -- PROGRAM ARG...` | `wsh --wsh-run --login -- PROGRAM ARG...` |
| `wsh run -- ZSH_ARGUMENTS...` | `wsh ZSH_ARGUMENTS...` |
| `wsh update` | DNF install/upgrade of the selected package |
| Bundle rollback | DNF downgrade to an available earlier package |

Native Wsh preserves Zsh command-line semantics. `--version` reports Zsh's version; `--` terminates shell option parsing. Words such as `doctor`, `profile`, `update` and `run` can name ordinary scripts, so they cannot be intercepted as deprecated manager commands. Use `--wsh-help` for the explicit native tool interface. Native profile reports preserve the tested schema-1 data; retain the legacy reporter for historical numeric values outside signed 64-bit range.

Wakterm's restore caller selects native foreground invocation for `/usr/bin/wsh` and `/bin/wsh`, preserving exact argument bytes and native job control. Per-user legacy Wsh and other shells retain their existing restore path. A native binary installed at another path needs a separately tested caller configuration.

## Package updates and recovery

For this development RPM, use `sudo dnf install ./wsh-native-development-*.rpm`, `sudo dnf upgrade ./NEW_PACKAGE.rpm`, or `sudo dnf downgrade ./OLDER_PACKAGE.rpm` with the intended single local package file. Future published package names and repository configuration require a release decision. There is no second native updater or mutable activation record.

Bundled modules are linked into each shell executable, so a running shell retains them when RPM replaces the executable. External module loading remains available and follows Zsh's ABI requirements. Autoload functions and the optional helper use the installed package's resources; this qualification covers the current Zsh ABI and helper protocol. Future incompatible function/protocol changes need an explicit compatibility or restart policy before shipping.

Ordinary package removal refuses while a local `/etc/passwd` entry names `/usr/bin/wsh` or `/bin/wsh`. Change those accounts to an installed alternative first. Remote identity directories and arbitrary aliases need administrator checks; bypassing scriptlets bypasses this guard. Missing shell executables, required system libraries, or damaged system files still require system recovery. Missing or malformed Wsh activation state, unavailable home configuration, or an unavailable optional helper does not prevent the tested native login path.
