# wsh

`wsh` is a fast, tested Zsh distribution with autosuggestions, history search, syntax highlighting and directory jumping built in. Keep your existing `.zshrc`, Oh My Zsh setup and familiar Zsh commands.

- Type less and spot mistakes sooner with built-in autosuggestions, history search and syntax highlighting: [35–91% shorter highlighting updates and 29% less autosuggestion editing time with large histories](PERFORMANCE.md) compared with the tested Zsh plugins.
- Jump back to frequently used directories with [`z`](NATIVE-INSTALLATION.md#directory-jumping), with [84% shorter lookup time](PERFORMANCE.md) than the tested Zsh plugin at 1,000 saved directories.
- Navigate large histories with [23–72% less editing time](PERFORMANCE.md) compared with the tested history-search plugin.
- Initialize completions with [20% shorter cold-start time](PERFORMANCE.md) compared with the tested Zsh compinit.
- Keep your existing Zsh theme, or choose Wsh’s built-in [Minimal, Wakamex, Robbyrussell, or Agnoster prompts](THEMES.md), with [up to 95% shorter prompt waits for Agnoster compared with OMZ](PERFORMANCE.md#built-in-prompts-compared-with-omz).
- [Find startup slowdowns](PROFILING.md) and use `wsh --doctor` to find plugins that duplicate features you already have.
- Use [terminal integration](TERMINAL-INTEGRATION.md) to jump between prompts, select command output, and open tabs in the current directory. Available features depend on your terminal.
- Make Wsh your default shell and manage installation and updates through [DNF](NATIVE-INSTALLATION.md).

## Compatibility

Use familiar Zsh commands, scripts, completions and Oh My Zsh configuration. Wsh bundles Zsh itself, so you keep its language, line editor and job control. Wsh's editing features also work with your existing prompt.

For supported plugins installed without modifications, Wsh can provide the same features more quickly while keeping supported settings. Plugins you have customized, or that Wsh cannot identify, continue to run as configured. Some features from newer plugin versions may not yet be available through Wsh; [component compatibility](VENDORED-COMPONENTS.md) records what is supported. Run `wsh --doctor` to find redundant setup and suggested cleanup. Doctor never edits your startup files.

## Install

On Fedora 44 x86-64, enable the [COPR repository](https://copr.fedorainfracloud.org/coprs/wakamex/wsh/) and install:

```sh
sudo dnf copr enable wakamex/wsh
sudo dnf install wsh
wsh --wsh-version
wsh -l
```

After testing your configuration, use `chsh -s /usr/bin/wsh` if you want it as your login shell. Keep the existing session open until a separate login succeeds. Update with `sudo dnf upgrade wsh`. The [installation guide](NATIVE-INSTALLATION.md) covers account setup, direct RPMs and recovery.

You can also [build from source](DEVELOPMENT.md#native-development-installation) and run the resulting installation on Linux; RPM and Fedora are not required. Other distributions need compatible build dependencies and system libraries. Local builds are unsigned development artifacts.

## Usage

| Task | Command |
| --- | --- |
| Open a shell | `wsh` |
| Inspect your setup without editing it | `wsh --doctor` |
| Find interactive startup slowdowns | `wsh --profile -- -i` |
| Read a saved profiling report | `wsh --profile-report DIRECTORY` |
| See the installed Wsh version | `wsh --wsh-version` |
| Run a program, then return to a Wsh prompt | `wsh --run -- PROGRAM ARG...` |
| List Wsh’s command options | `wsh --wsh-help` |

Foreground programs retain normal Ctrl-C, Ctrl-Z and `fg` behavior. See [profiling](PROFILING.md) for interpreting startup measurements and [the command reference](NATIVE-INSTALLATION.md#commands) for Zsh argument handling.

## Prompt selection

Wsh preserves your existing prompt when `WSH_THEME` is unset or empty. Try a built-in theme for one Wsh session:

```sh
WSH_THEME=wakamex wsh
```

Choose `minimal`, `wakamex`, `robbyrussell`, or `agnoster`. Selecting Robbyrussell or Agnoster through OMZ uses the OMZ version; select it through `WSH_THEME` to get Wsh's version and its measured performance benefits. [The theme guide](THEMES.md) covers appearance, custom layouts and colors, and differences from the OMZ versions.

Choose how to configure it:

- Keep using Zsh and Wsh interchangeably: leave `.zshrc` unchanged and select a Wsh theme with the command above. Zsh keeps your existing theme.
- Switch entirely to Wsh: set `WSH_THEME=wakamex` in `.zshrc`. If you keep OMZ, set `ZSH_THEME=""` before sourcing it to skip its theme.
- Optionally avoid loading the OMZ theme in Wsh while keeping it in Zsh: add the [shared-configuration conditional](THEMES.md#session-selection-and-shared-configuration). This saves duplicate theme work; it is not required to use both shells.

## Testing and bundled Zsh

Tests cover installation, login, suspending and resuming programs, recovery and login after a reboot on Fedora with its SELinux security protections enabled. Two separate builds also produced identical packages. See the [package qualification report](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/release-qualification-2026-09-10/report.md) and [Fedora source-build results](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/source-rpm-2026-09-11/report.md) for the tested versions and configurations.

The bundled Zsh incorporates 1,074 upstream commits since Zsh 5.9 ([upstream NEWS](https://github.com/zsh-users/zsh/blob/cad0d67c76e2be7371cf3526b79ea2581810d35a/NEWS), [Wsh validation](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/edge-zsh-2026-09-03/report.md)). Wsh-maintained fixes correct [terminal prompt and directory reporting](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-terminal-integration-2026-09-04/report.md), make [compiled-function files reproducible](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/zcompile-reproducibility-2026-09-04/report.md), and prevent [obsolete highlighting data from accumulating](UPSTREAM-ZSH-BUGS.md#neutral-highlight-attributes-discard-ownership-metadata). The [source definition](build/zsh-sources/zsh-cad0d67c-native.json) records the exact Zsh version and included patches.

## Documentation

- User guides: [installation and commands](NATIVE-INSTALLATION.md), [themes](THEMES.md), [profiling](PROFILING.md), and [terminal integration](TERMINAL-INTEGRATION.md).
- Evaluation and trust: [performance results](PERFORMANCE.md), [component compatibility](VENDORED-COMPONENTS.md), [security](SECURITY.md), and [release verification](RELEASES.md).
- Development: [architecture](DESIGN.md), [building and testing](DEVELOPMENT.md), [source RPMs](packaging/SOURCE-RPM.md), and [future feature priorities](FEATURES.md).

## License

Original `wsh` work is available under the [MIT License](LICENSE). Bundled or adapted third-party components retain their own licenses and notices.
