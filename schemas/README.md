# Schemas

`bundle.schema.json` describes unsigned local development manifests accepted by the initial manager. Official signed release metadata is intentionally absent from schema 1.

`theme.schema.json` describes the data model obtained after decoding a theme TOML file. The Rust parser also enforces cross-field rules that JSON Schema cannot express cleanly, including agreement between component enablement and layout membership and the required prompt character.

`runtime-protocol-v1.md` fixes the bounded request, response, Git snapshot, cancellation, and repaint contract between the bundled Zsh adapter and runtime.

Both schemas reject unknown fields. Theme literals are bounded and cannot contain terminal control characters, and bundle paths are rechecked by the manager with filesystem-aware path and file-type validation.

Optional theme segment styling uses named palette colors and the existing component names. The Rust validator also requires styled components to be enabled and restricts dirty-background to Git. Theme ports and examples are documented in [THEMES.md](../THEMES.md).
