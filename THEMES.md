# Wsh themes

Select a theme with `WSH_THEME=minimal`, `WSH_THEME=wakamex`, `WSH_THEME=robbyrussell`, `WSH_THEME=agnoster`, or a definition path. An unset or empty value preserves the existing prompt. The [shared-configuration instructions](README.md#prompt-selection) describe coexistence with OMZ.

| Name | Presentation |
| --- | --- |
| minimal | Short directory, explicit Git state, colored prompt character, and duration on the right |
| wakamex | Changed-only directory display, compact Git state, command duration, and SSH context |
| robbyrussell | Leading green/red status arrow, cyan short directory, and blue git:(branch) labels with separate changed-file indicators |
| agnoster | Full directory in a blue Powerline segment, green clean Git or yellow dirty Git segment, optional SSH context, and failure/privilege indicators |

Robbyrussell and Agnoster are Wsh ports of the OMZ presentations at commit `9112b53fa8b5ab556c7c893aa8be8a247ac512a0`. Attribution is retained in [OMZ-LICENSE.txt](themes/OMZ-LICENSE.txt). They use Wsh's Git fields and trusted renderer, and do not execute the OMZ theme files. Wsh shows its own separate staged, modified, and untracked indicators. The Agnoster port covers directory, Git, SSH context, exit status, and privilege; it does not reproduce OMZ's virtualenv, background-job, Mercurial, or Bazaar components. Agnoster requires a terminal font with Powerline separator glyphs.

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
