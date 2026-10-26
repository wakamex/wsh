# Wsh themes

Select a theme with `WSH_THEME=minimal`, `WSH_THEME=wakamex`, `WSH_THEME=robbyrussell`, `WSH_THEME=agnoster`, or a definition path. An unset or empty value preserves the existing prompt.

| Name | Presentation |
| --- | --- |
| minimal | Short directory, explicit Git state, colored prompt character, and duration on the right |
| wakamex | Changed-only directory display, compact Git state, command duration, and SSH context |
| robbyrussell | Leading green/red status arrow, cyan short directory, and blue git:(branch) labels with separate changed-file indicators |
| agnoster | Full directory in a blue Powerline segment, green clean Git or yellow dirty Git segment, optional SSH context, and failure/privilege indicators |

Robbyrussell and Agnoster are Wsh ports of the OMZ presentations at commit `9112b53fa8b5ab556c7c893aa8be8a247ac512a0`. Attribution is retained in [OMZ-LICENSE.txt](themes/OMZ-LICENSE.txt). They use Wsh's Git fields and trusted renderer, and do not execute the OMZ theme files. Wsh shows its own separate staged, modified, and untracked indicators. The Agnoster port covers directory, Git, SSH context, exit status, and privilege; it does not reproduce OMZ's virtualenv, background-job, Mercurial, or Bazaar components. Agnoster requires a terminal font with Powerline separator glyphs.

## Session selection and shared configuration

Wsh preserves your existing prompt when `WSH_THEME` is unset or empty. Select a built-in theme to keep typing while its Git status updates:

```sh
WSH_THEME=wakamex wsh
WSH_THEME=minimal wsh
WSH_THEME=robbyrussell wsh
WSH_THEME=agnoster wsh
WSH_THEME=/path/to/theme.toml wsh
```

Run these commands in your terminal to try a theme for that Wsh session. You can customize layout and colors in a theme file without writing shell scripts. Selecting Robbyrussell or Agnoster through OMZ uses the OMZ version; select it through `WSH_THEME` to get Wsh's version and its measured performance benefits. The presentation table above describes which OMZ features the ports cover; the definition format below explains customization.

Built-in themes read Git status without taking the repository's index lock, so a status never holds `index.lock` while you run `git add` or `git commit`. Without the lock, Git cannot save the file timestamps it rechecks, so a repository whose files were touched without changing, for example by a build or a checkout, would recheck them at every prompt. Git cannot both take the lock and leave it free for you: a status that may take the lock creates `index.lock` on every run even when it has nothing to write, which is the Git behavior a [proposed fix](https://lore.kernel.org/git/20261022184420.3648771-1-mcosma@gmail.com/) changes. When a status takes 100 ms or more, or runs past the prompt's 2-second limit, Wsh refreshes the index once in the background: Git rehashes a private copy, and Wsh then takes `index.lock` only to replace the index with that copy, and only if the index is unchanged and the copy has new timestamps. A `git add` or `git commit` can therefore meet the lock only in the moment of that file copy and rename, and the refresh gives way to any change you make meanwhile. It skips the refresh while `index.lock` exists, during a rebase, merge, cherry-pick, revert or bisect, with a split index, and when `GIT_INDEX_FILE` is set, and a later batch of touched files is refreshed again. Git starts the refresh in the second after the slow status, because Git trusts an index entry only when its file is older than the index by the second, and a status that cannot help is retried after 2 seconds, then 4, up to 5 minutes. Set `WSH_GIT_REFRESH_LOG` to a file path to record, with a timestamp and process ID, each status's duration and each refresh decision and outcome. In a 20,000-file repository with touched files, the first prompt took 230 ms and later prompts 17 ms. The background refresh is a workaround: once a Git release with that fix is common, the prompt's status can take the lock itself and the refresh can go.

If you use Zsh and Wsh interchangeably, you can leave your shared `.zshrc` unchanged and select the Wsh theme on the command line as above. OMZ loads its existing theme, then Wsh installs the selected prompt. Any theme work and unrelated hooks from OMZ still run.

If you switch entirely to Wsh, set `WSH_THEME=wakamex` in `.zshrc`. If OMZ still loads, set `ZSH_THEME=""` before sourcing `oh-my-zsh.sh`. Removing OMZ is a separate choice; its other plugins and configuration can remain useful.

The following conditional is an optional optimization for using both shells: it skips OMZ's theme when a Wsh theme is selected on the command line, while retaining the OMZ theme in regular Zsh. Put it after your existing `ZSH_THEME` assignment and before sourcing `oh-my-zsh.sh`:

```zsh
if [[ -n ${WSH_THEME-} ]]; then
  ZSH_THEME=""
fi
```

To select Wsh's prompt from the shared file itself, test `WSH_VERSION` instead. Wsh sets it to its version before any startup file runs and does not export it, so a regular Zsh started from Wsh does not see it:

```zsh
if [[ -n ${WSH_VERSION-} ]]; then
  WSH_THEME="wakamex"
  ZSH_THEME=""
fi
```

Wsh keeps `WSH_THEME` local to its session so nested regular Zsh does not inherit it. Avoid unconditionally assigning or globally exporting `WSH_THEME` in a shared configuration: the first conditional would suppress your OMZ theme in regular Zsh too. Selection takes effect after `.zshrc`; changing it later does not switch the current prompt. If the selected definition is missing or invalid, Wsh reports the failure and leaves the prompt from user startup in place.

`WSH_THEME=wakamex wsh --doctor` checks the same startup choice. If OMZ still has a theme configured alongside Wsh's prompt, doctor suggests the first conditional above or clearing `WSH_THEME`. Use the conditional to avoid loading two themes in Wsh while keeping your OMZ theme in regular Zsh. Keep any plugin declarations needed by regular Zsh when following further cleanup advice.

## Definition format

Definitions are TOML data validated by the runtime against a strict schema. [The JSON Schema](schemas/theme.schema.json) describes the decoded structure; the native validator additionally checks layout membership and component enablement. Unknown fields, unrecognized colors, oversized literals, and control characters are rejected. Literal text and provider values are escaped for Zsh prompt expansion. Definitions cannot source files, execute commands, or inject terminal escapes.

The left and right layouts contain each enabled component at most once: context, cwd, git, duration, or prompt-character. A prompt character must be enabled and present. The existing theme files provide complete examples of the required component fields.

Optional `git.label-suffix` closes a branch, tag, or detached label, as in robbyrussell's closing parenthesis. Optional segment entries add bounded background styling:

```toml
[segments.cwd]
background = "blue"

[segments.git]
background = "green"
dirty-background = "yellow"
```

Segment keys must name enabled layout components. Colors use the existing named palette. Only Git accepts dirty-background, selected when staged, modified, or untracked files are present. The trusted renderer supplies Powerline transitions and resets the background at segment boundaries; definitions cannot provide raw styling escapes. Existing definitions without segments retain their previous rendering behavior.
