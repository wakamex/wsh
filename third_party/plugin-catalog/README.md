# Upstream plugin recognition catalog

`catalog.json` records exact upstream snapshots whose startup state can be handed to Wsh's current implementation. An uncataloged version continues to run externally. Recognition authorizes a component-specific handoff; it does not select an old implementation or claim compatibility with every upstream version.

Each entry records the component, version or snapshot label, upstream repository, immutable revision, upstream file paths, SHA-256 fingerprints and handoff family. Multi-file components match one complete entry; files from different versions are not combined. Source bytes in `snapshots/` are unchanged upstream files and retain their embedded license notices. Entries referencing other `third_party` directories retain those components' existing license and provenance files.

The build verifies every fingerprint and emits a compact component-to-reference table. Startup compares bounded file contents in process, using the existing Zsh file-reading builtins. The installed references are deduplicated by SHA-256. Wsh never executes them. A runtime hashing interface is unnecessary for this initial catalog; the exact reference bytes are also useful for reproducing handoff tests.

## Adding a snapshot

1. Read the source from an immutable upstream Git revision. Verify that the revision is upstream, rather than merely the HEAD of a user's fork. Record its repository, revision and upstream paths.
2. Retain the exact relevant files under `snapshots/SHA256`, or reference an existing vendored copy. Preserve its license. Add the entry and its handoff family to `catalog.json`.
3. Run `python3 build/plugin-catalog.py --check`, then build a development installation.
4. Run `python3 native/test-plugin-catalog.py INSTALLATION OUTPUT`. Every entry receives real interactive startup, customization and ownership checks. Autosuggestion and history entries also exercise the editor. Existing component suites test the current native implementation more deeply.
5. Run the host and canonical floor contracts, retain matched startup measurements and update the accepted evidence verifier. Expand a handoff rule only when a concrete test establishes the need.

Settings remain user-owned. Implementation-function overrides, unsafe active state, unknown source and missing files prevent automatic takeover. Recognition does not rely on version strings, directory names or Git metadata found in the user's installation. No startup network request or automatic plugin update is introduced.

## Autosuggestion lifecycle hooks

Before v0.6.0, upstream excluded all `zle-*` widgets inside its binder. v0.6.0 moved that rule into the configurable ignore list, explicitly allowing users to opt lifecycle widgets in. The v0.5.2 handoff therefore adds `zle-*` to the inherited list to preserve its formerly implicit exclusion. Later versions retain the user's list unchanged, including lifecycle opt-ins. The matrix checks both old-version suggestion behavior and an explicitly wrapped `zle-line-init` hook in later versions.
