# Upstream activity reviewed September 10, 2026

These plugins have relatively infrequent releases, but their history includes changes to lifecycle, defaults and persistence. Upstream provenance alone does not establish a safe handoff to a replacement implementation.

| Component | Latest upstream commit checked | Latest stable release or tag | Relevant changes |
|---|---|---|---|
| Autosuggestions | [June 24, 2025](https://github.com/zsh-users/zsh-autosuggestions/commit/85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5) | v0.7.1, November 15, 2024 | v0.7.0 enabled asynchronous suggestions by default. v0.6.0 moved the lifecycle-widget exclusion from the binder into user configuration, explicitly permitting opt-in. |
| History substring search | [January 15, 2026](https://github.com/zsh-users/zsh-history-substring-search/commit/14c8d2e0ffaee98f2df9850b19944f32546fdea5) | [v1.1.0, July 28, 2023](https://github.com/zsh-users/zsh-history-substring-search/releases/tag/v1.1.0) | Changed highlighting-hook integration and stopped overwriting initialized configuration with defaults. |
| Syntax highlighting | [August 22, 2026](https://github.com/zsh-users/zsh-syntax-highlighting/commit/2fc57d63067c18b1100ecdbf684fa5baf49459d1), a test-documentation change | 0.7.1, February 28, 2020 | Development switched from widget wrapping to redraw hooks on supported Zsh versions. |
| Zsh-z | [August 14, 2026](https://github.com/agkozak/zsh-z/commit/102fb78036ed76feedf623907483691777a1d510) | [v2.0.0, August 14, 2026](https://github.com/agkozak/zsh-z/releases/tag/v2.0.0) | Reworked background writes and locking. Combining `-r` and `-t` now errors. Database format and existing settings remain compatible. OMZ imported this version on August 16. |
| OMZ Git-prompt | [April 19, 2025](https://github.com/ohmyzsh/ohmyzsh/commit/a7426f0b38817bf7cd7000a5d378b7cfb059884f) | Distributed with OMZ | Fixed stash counting for worktrees using the common Git directory. |

The [autosuggestion changelog](https://github.com/zsh-users/zsh-autosuggestions/blob/master/CHANGELOG.md) documents both the asynchronous default change and the deliberate lifecycle opt-in. The [highlighting changelog](https://github.com/zsh-users/zsh-syntax-highlighting/blob/master/changelog.md) describes the redraw-hook migration and its compatibility fixes. Latest repository activity can be documentation or tests; these dates are not all runtime-code changes. The dated official API responses are retained with the experiment inputs.
