# Account login and Wsh recovery

Keep an OS-managed shell such as `/bin/bash` or system Zsh in your account's login-shell field, and configure your terminal to start `wsh`. The Wsh installer does not change your account shell or `/etc/shells`. Copying the launcher system-wide does not install an active bundle for every account.

Wsh must read activation state before it can start bundled Zsh. It chooses state from `WSH_STATE_ROOT`, then `$XDG_DATA_HOME/wsh`, then `$HOME/.local/share/wsh`. Those variables must already exist in the launch environment; `.zshenv` has not run yet. A graphical login service or a fresh TTY can therefore look in a different location from a configured terminal even when the bundle and its state still exist.

## Recovery in current development

The recovery behavior described here is implemented in development after v0.3.1. Released v0.3.1 and earlier terminate on unusable activation state and do not implement this recovery path.

The launcher recognizes a leading `-` in Unix login argv[0], such as `-wsh`, and ordinary shell invocations such as `wsh -c 'command'` and `wsh -lc 'command'`. With usable state it starts bundled Zsh, preserves login startup when requested, and passes arguments directly to Zsh. An executed command's exit status remains its exit status.

If bundle selection or the exec syscall fails, supported shell invocations start `/bin/bash --noprofile --norc` at the same user identity. Recovery prints the original failure and a notice, sets `SHELL=/bin/bash`, and removes inherited Wsh integration and Bash startup-injection settings. It never looks up a fallback through PATH or the old SHELL value. The interactive prompt is `wsh recovery$ `, with native Bash job control. User Bash startup files, BASH_ENV, ENV, PROMPT_COMMAND, PS0, imported functions, and inherited Bash option settings cannot restart Wsh during this recovery startup.

Recovery accepts login, interactive, stdin, and command flags (`-l`, `-i`, `-s`, `-c`, their short combinations, and `--login`). The command string and remaining positional arguments are passed as exact argv, including non-UTF-8 bytes. Shell-specific flags, restricted-shell options, and script filenames are not translated to Bash. A command executed during recovery uses Bash semantics; it does not gain Zsh language compatibility.

Manager commands such as `wsh update`, `wsh bundle rollback`, and `wsh run` retain their errors. Recovery does not alter activation state, automatically roll back, fetch a release, modify account configuration, or supervise an already running Zsh.

## Repair from the recovery shell

Return the account to an installed OS shell with `chsh -s /bin/bash`, or have an administrator change it if your account policy requires that. Check whether the login environment selects the intended state location. If a previous verified bundle exists in valid state, `wsh bundle rollback` can restore it offline. If activation state is missing or corrupt, reinstall an official release from the README's installer command or explicitly activate an already verified bundle. `wsh update` itself needs usable active release state.

## Recovery requires an executable launcher and system Bash

This pre-exec recovery handles missing, unreadable, malformed, incompatible, or symlink activation state; missing bundles; changed entrypoint metadata; and exec-time failures such as a missing interpreter. It cannot run if the launcher has been removed, is denied execution by permissions or SELinux, or cannot load its own system libraries. It also cannot recover a dynamic-loader failure after exec has succeeded, user Zsh startup code that exits or hangs, a broken system Bash, or failures in PAM and the display manager before shell invocation. These are reasons to keep the account shell independent of Wsh's per-user installation.

The regression uses real execve login argv[0], raw command invocations, and a PTY with suspension, foreground resume, interruption, and prompt return. It does not modify real accounts or claim to reproduce a full GDM/PAM login. The reported Fedora incident's original state was not available; the fresh-account reproduction proves missing-state behavior, not that an update deleted the original account's state.

## Native system-package development

The native development executable starts Zsh directly without consulting activation state. The [local Fedora RPM prototype](packaging/README.md) passes actual fresh-account PAM/TTY login, enforcing SELinux including a confined user, authenticated `chsh`, unavailable optional components, and reboot. Package upgrade/downgrade and local-account removal behavior are covered by [retained VM tests](benchmarks/native-package-2026-09-08/report.md). This path is under migration development and is not yet a published installation method. The release recommendation at the start of this document continues to apply to the current per-user launcher.
