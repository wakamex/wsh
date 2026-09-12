# Native package installation

Wsh installs as an x86-64 Fedora RPM. The package owns `/usr/bin/wsh`, its `/bin/wsh` alias on Fedora, and resources under `/usr/libexec/wsh`. The native release assumes fresh installations. Compatibility with existing Zsh configuration, Oh My Zsh and supported plugin settings remains part of the product; compatibility with earlier Wsh launchers and manager commands is not a release requirement.

## Installation and account shell

Native packages have not been published yet. Build instructions are in [DEVELOPMENT.md](DEVELOPMENT.md); local artifacts are unsigned development builds. Test a selected RPM in an isolated machine with an independent recovery account. Replace the placeholder filename with the actual package:

```sh
sudo dnf install ./wsh-VERSION-RELEASE.x86_64.rpm
/usr/bin/wsh --wsh-version
/usr/bin/wsh --doctor
/usr/bin/wsh -l
```

After testing your configuration and terminal behavior, use `chsh -s /usr/bin/wsh` if you want Wsh as your login shell. Keep the existing session open until a separate login succeeds. The package registers its supported paths in `/etc/shells`. Login does not read per-user activation records.

## Commands

| Task | Command |
| --- | --- |
| Interactive shell | `wsh` |
| Distribution identity | `wsh --wsh-version` |
| Zsh version | `wsh --version` |
| Diagnostics | `wsh --doctor` |
| Interactive startup profile | `wsh --profile -- -i` |
| Function-level profile | `wsh --profile --functions -- -i` |
| Saved profile report | `wsh --profile-report DIRECTORY` |
| Foreground application, then prompt | `wsh --wsh-run -- PROGRAM ARG...` |
| Native tool help | `wsh --wsh-help` |

Wsh preserves Zsh command-line parsing: `--` ends option parsing, ordinary positional arguments name shell scripts, and `-c`, `-s` and `-f` keep their Zsh meanings. See [PROFILING.md](PROFILING.md) for profile options and reports.

## Directory jumping

Wsh supplies `z` when your configuration has not already defined a directory-jump command. Visit a directory, then use part of its name to return:

```sh
cd /code/my-project
cd /tmp
z my-project
```

Wsh learns which directories you visit most often and most recently, saving them in `~/.z`. You can keep your existing OMZ `z` history and `ZSHZ_*` settings, including `ZSHZ_DATA` for another database path and `ZSHZ_CMD` for another command name. If you use Zoxide or a directory-jump command that Wsh cannot identify as a supported plugin, Wsh leaves it in place. Set `WSH_DISABLE_DIRECTORY_JUMP=1` in `.zshrc` to disable Wsh's default. Tab completion uses your existing Zsh completion setup.

## Package updates and recovery

For a selected native RPM, use `sudo dnf install ./wsh-VERSION-RELEASE.x86_64.rpm`, `sudo dnf upgrade ./NEW_PACKAGE.rpm`, or `sudo dnf downgrade ./OLDER_PACKAGE.rpm` with the intended single local package file. The package name is `wsh`. A hosted DNF repository is not configured. There is no second native updater or mutable activation record.

Bundled modules are linked into each shell executable, so a running shell retains them when RPM replaces the executable. External module loading remains available and follows Zsh's ABI requirements. Autoload functions and the optional helper use the installed package's resources; this qualification covers the current Zsh ABI and helper protocol. Future incompatible function/protocol changes need an explicit compatibility or restart policy before shipping.

Ordinary package removal refuses while a local `/etc/passwd` entry names `/usr/bin/wsh` or `/bin/wsh`. Change those accounts to an installed alternative first. Remote identity directories and arbitrary aliases need administrator checks; bypassing scriptlets bypasses this guard. Missing shell executables, required system libraries, or damaged system files still require system recovery. Missing or malformed Wsh activation state, unavailable home configuration, or an unavailable optional helper does not prevent the tested native login path.

## Verified login coverage

The [Fedora QEMU qualification](benchmarks/release-qualification-2026-09-10/report.md) exercises real serial-getty/PAM login, prompt readiness, Ctrl-Z, `fg`, Ctrl-C, authenticated unprivileged `chsh`, enforcing SELinux with a confined account and login after reboot. Missing optional helper or integration resources preserve the tested native shell path. Package verification passes after restoring the deliberately removed resources.

This covers actual TTY/PAM login, not a complete graphical GDM session. Broken user startup code and failures in PAM or a display manager require recovery at their respective owners; the package removal guard cannot prevent those failures. [Package behavior](packaging/README.md) and the [release contract](RELEASES.md) record the corresponding distribution checks.
