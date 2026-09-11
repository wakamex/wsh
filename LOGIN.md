# Native account-shell support

The native RPM installs Wsh at `/usr/bin/wsh` and registers `/usr/bin/wsh` and `/bin/wsh` in `/etc/shells`. Zsh starts directly from the system-owned executable. Login does not depend on a per-user bundle activation record, updater or recovery launcher.

## Select Wsh as the login shell

Follow the [native installation guide](NATIVE-INSTALLATION.md). Test `/usr/bin/wsh -l` with your configuration before using `chsh -s /usr/bin/wsh`. Keep the existing session open until a separate login succeeds. Native packages have not been published yet; local development RPMs should be tested in an isolated machine with an independent recovery account.

## Verified login and recovery behavior

The [fresh Fedora QEMU qualification](benchmarks/release-qualification-2026-09-10/report.md) passes real serial-getty/PAM login, prompt readiness, Ctrl-Z, `fg`, Ctrl-C, authenticated unprivileged `chsh`, enforcing SELinux with a confined account and login after reboot. Missing or unusable legacy activation state and optional helper/integration resources preserve access to the native shell. Package verification passes after restoring the deliberately removed resources.

Ordinary RPM removal refuses while a local `/etc/passwd` entry names either registered Wsh path. Change those accounts to another installed shell before removal. Remote identity services and arbitrary shell aliases require administrator checks. Package updates and downgrades use DNF; there is no Wsh self-updater.

The system-owned executable and its required libraries must remain available. Forced file deletion, scriptlet bypass, broken user startup code, and failures in PAM or a display manager require recovery at their respective owner. The QEMU test exercises actual TTY/PAM login; it does not establish a complete graphical GDM session. See [package behavior](packaging/README.md) and the [release contract](RELEASES.md).
