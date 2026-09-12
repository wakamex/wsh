# wsh

`wsh` is a fast, tested Zsh distribution with autosuggestions, history search, syntax highlighting and directory jumping built in. Keep your existing `.zshrc`, Oh My Zsh setup and familiar Zsh commands.

Wsh’s Fedora packages are still in development and have not been published.

- Type less with autosuggestions and history substring search, and spot mistakes with syntax highlighting built in.
- Jump back to frequently used directories with `z`.
- Keep your existing Zsh theme, or choose Wsh’s built-in Minimal, Wakamex, Robbyrussell, or Agnoster prompts, with [up to 95% shorter prompt waits for Agnoster compared with OMZ](PERFORMANCE.md#built-in-prompts-compared-with-omz).
- Find which parts of your configuration slow startup and which plugins duplicate features you already have.
- Make Wsh your default shell and install, update or downgrade it through Fedora’s package manager, DNF.
- Jump between prompts, select command output, and open new tabs in the current directory in compatible terminals.

Spend less time waiting as you edit: syntax-highlighting updates took 35–91% less time with Wsh, and editing with autosuggestions took 29% less time in tests with 10,000 history entries. Both comparisons used the corresponding Zsh plugins as baselines. See [performance results](PERFORMANCE.md) for the tested commands and measurements.

Get [up to 95% shorter prompt waits](PERFORMANCE.md#built-in-prompts-compared-with-omz) with Wsh’s built-in Agnoster compared with OMZ Agnoster in the tested Git repositories. Wsh’s Robbyrussell also displayed updated Git status about 9 ms sooner than OMZ’s version. The [theme comparison](PERFORMANCE.md#built-in-prompts-compared-with-omz) explains the tested repositories and the difference between being able to type and seeing updated Git status.

## Compatibility

Use familiar Zsh commands, scripts, completions and Oh My Zsh configuration. Wsh bundles Zsh itself, so you keep its language, line editor and job control.

For supported plugins installed without modifications, Wsh can provide the same features more quickly while keeping supported settings. Plugins you have customized, or that Wsh cannot identify, continue to run as configured. Some features from newer plugin versions may not yet be available through Wsh; [component compatibility](VENDORED-COMPONENTS.md) records what is supported. Run `wsh --wsh-doctor` to find redundant setup and suggested cleanup. Doctor never edits your startup files.

Wsh's editing features also work with your existing prompt.

## Motivation

Setting up a comfortable Zsh environment often means assembling plugins, themes and terminal integration yourself. Those pieces can repeat work or delay the next prompt. Wsh supplies tested defaults, helps identify redundant configuration and measures whether changes improve everyday editing and prompt response. [MOTIVATION.md](MOTIVATION.md) records the comparisons behind that direction; [DESIGN.md](DESIGN.md) describes the implementation.

## Install

Wsh currently supports 64-bit x86 Fedora installations. Until packages are published, testing requires building an unsigned development package. See [DEVELOPMENT.md](DEVELOPMENT.md) for build instructions or [the source-RPM guide](packaging/SOURCE-RPM.md) to build a package using your Fedora release’s libraries.

Once you have built an RPM package, replace the filename below with its actual name. Try it on a test machine where you can still log in to another account using an existing shell:

```sh
sudo dnf install ./wsh-VERSION-RELEASE.x86_64.rpm
/usr/bin/wsh --wsh-version
/usr/bin/wsh -l
```

After testing your configuration, use `chsh -s /usr/bin/wsh` if you want it as your login shell. Keep the existing session open until a separate login succeeds. The [installation guide](NATIVE-INSTALLATION.md) covers commands, package updates and recovery.

Install upgrades and downgrades explicitly through DNF using the selected RPM. There is no hosted DNF repository yet.

Run `wsh` to open a shell, `wsh --wsh-doctor` to inspect your setup, and `wsh --wsh-version` to see the installed version. Use `wsh --wsh-profile -- -i` to find startup slowdowns. `wsh --wsh-run -- PROGRAM ARG...` starts a program and returns to a Wsh prompt when it exits, with Ctrl-C, Ctrl-Z and `fg` available as usual. See [PROFILING.md](PROFILING.md) for reading and recovering profiling reports.

## Directory jumping

Wsh supplies `z` when your configuration has not already defined a directory-jump command. Visit a directory, then use part of its name to return:

```sh
cd /code/my-project
cd /tmp
z my-project
```

Wsh learns which directories you visit most often and most recently, saving them in `~/.z`. You can keep your existing OMZ `z` history and `ZSHZ_*` settings, including `ZSHZ_DATA` for another database path and `ZSHZ_CMD` for another command name. If you use Zoxide or a directory-jump command that Wsh cannot identify as a supported plugin, Wsh leaves it in place. Set `WSH_DISABLE_DIRECTORY_JUMP=1` in `.zshrc` to disable Wsh's default. Tab completion uses your existing Zsh completion setup.

## Prompt selection

Wsh preserves your existing prompt when `WSH_THEME` is unset or empty. Select a built-in theme to keep typing while its Git status updates:

```sh
WSH_THEME=wakamex wsh
WSH_THEME=minimal wsh
WSH_THEME=robbyrussell wsh
WSH_THEME=agnoster wsh
WSH_THEME=/path/to/theme.toml wsh
```

Run these commands in your terminal to try a theme for that Wsh session. You can customize layout and colors in a theme file without writing shell scripts. Selecting Robbyrussell or Agnoster through OMZ uses the OMZ version; select it through `WSH_THEME` to get Wsh's version and its measured performance benefits. [THEMES.md](THEMES.md) describes customization and which OMZ features the ports cover.

In a shared `.zshrc`, put this after your existing `ZSH_THEME` assignment and before sourcing `oh-my-zsh.sh`:

```zsh
if [[ -n ${WSH_THEME-} ]]; then
  ZSH_THEME=""
fi
```

Regular Zsh continues to load your OMZ theme when `WSH_THEME` is unset. Wsh keeps the theme selection local to its session so nested regular Zsh does not inherit it. Avoid unconditionally assigning or globally exporting `WSH_THEME` in a shared configuration: the conditional would suppress your OMZ theme in regular Zsh too. Selection takes effect after `.zshrc`; changing it later does not switch the current prompt. If the selected definition is missing or invalid, Wsh reports the failure and leaves the prompt from user startup in place.

`WSH_THEME=wakamex wsh --wsh-doctor` checks the same startup choice. If OMZ still has a theme configured alongside Wsh's prompt, doctor suggests the conditional above or clearing `WSH_THEME`. Use the conditional to avoid loading two themes in Wsh while keeping your OMZ theme in regular Zsh. Keep any plugin declarations needed by regular Zsh when following further cleanup advice.

## Validation and Zsh fixes

Tests cover installation, login, suspending and resuming programs, recovery and login after a reboot on Fedora with its SELinux security protections enabled. Two separate builds also produced identical packages. See the [package qualification report](benchmarks/release-qualification-2026-09-10/report.md) and [Fedora source-build results](benchmarks/source-rpm-2026-09-11/report.md) for the tested versions and configurations.

The bundled Zsh incorporates 1,074 upstream commits since Zsh 5.9 ([upstream NEWS](https://github.com/zsh-users/zsh/blob/cad0d67c76e2be7371cf3526b79ea2581810d35a/NEWS), [Wsh validation](benchmarks/edge-zsh-2026-09-03/report.md)). It also includes Wsh-maintained fixes:

- Terminal navigation keeps working with correctly marked prompts, and new tabs can use the shell’s current directory after applications change the directory reported to the terminal. See the [terminal integration results](benchmarks/native-terminal-integration-2026-09-04/report.md).
- Repeated package builds can produce identical files after a fix to Zsh’s compiled-function output. See the [reproducibility results](benchmarks/zcompile-reproducibility-2026-09-04/report.md).
- Editing sessions avoid a buildup of obsolete highlighting data caused by a Zsh cleanup bug. See the [upstream candidate and reproducer](UPSTREAM-ZSH-BUGS.md#neutral-highlight-attributes-discard-ownership-metadata).

Available prompt navigation, output selection and directory inheritance depend on your terminal; [TERMINAL-INTEGRATION.md](TERMINAL-INTEGRATION.md) describes the supported behavior. The exact Zsh version and included patches are recorded in the [source definition](build/zsh-sources/zsh-cad0d67c-native.json).

## Under consideration

Possible additions include completions supplied by applications, separate command history for each terminal pane, help diagnosing terminal compatibility problems, and a directory of contributed themes. These are not available yet. [FEATURES.md](FEATURES.md) records the priorities and the evidence needed before adding them.

## Documentation

- [MOTIVATION.md](MOTIVATION.md) explains the problems Wsh addresses and the comparisons behind its priorities.
- [DESIGN.md](DESIGN.md) explains Wsh’s architecture.
- [IMPLEMENTATION.md](IMPLEMENTATION.md) records what has been implemented and tested.
- [PROFILING.md](PROFILING.md) explains how to find startup costs and read profiling reports.
- [PERFORMANCE.md](PERFORMANCE.md) collects measured editing, completion and prompt improvements.
- [THEMES.md](THEMES.md) covers theme selection and customization.
- [NATIVE-INSTALLATION.md](NATIVE-INSTALLATION.md) covers installation, login-shell setup and recovery.
- [DEVELOPMENT.md](DEVELOPMENT.md) explains how to build, test and contribute changes.
- [FEATURES.md](FEATURES.md) lists possible future features and their priorities.
- [SECURITY.md](SECURITY.md) and [RELEASES.md](RELEASES.md) explain security boundaries and how to verify official packages.
- [VENDORED-COMPONENTS.md](VENDORED-COMPONENTS.md) lists included components, their versions and compatibility details.

## License

Original `wsh` work is available under the [MIT License](LICENSE). Bundled or adapted third-party components retain their own licenses and notices.
