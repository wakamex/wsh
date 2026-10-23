# Recognized highlighting implementation e6683f2

`main-highlighter.zsh` comes unchanged from zsh-users/zsh-syntax-highlighting commit `e6683f20e5c38d3e5447f45845d04ddda75d0f23`, verified against the upstream Git blob `8531e5883103c4145f584b6c5e81edb7c99e185f`. It is a comparison input, never sourced by Wsh. The commit's `zsh-syntax-highlighting.zsh` is identical to the pinned copy in the parent directory, so the catalog entry uses that file. The parent component's `COPYING.md` applies.

The commit stops `_zsh_highlight_highlighter_main_check_path` from looping when `$PWD` has been deleted. Wsh's native main highlighter checks `ZSH_HIGHLIGHT_DIRS_BLACKLIST` by prefix comparison without walking parent directories, so the handoff is unaffected.

| File | SHA-256 |
|---|---|
| `main-highlighter.zsh` | `1f59176bc1e5fd8ac8eaa85dd7a4cd2a95083ee7c689a430ff4a5e2e9eee0061` |
