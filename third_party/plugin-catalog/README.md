# Upstream plugin recognition catalog

`catalog.json` records exact upstream snapshots whose startup state can be handed to Wsh's current implementation. An uncataloged Git checkout can also qualify through the local upstream check below. Recognition authorizes a component-specific handoff; it does not select an old implementation or claim compatibility with every upstream version.

Each entry records the component, version or snapshot label, upstream repository, immutable revision, upstream file paths, SHA-256 fingerprints and handoff family. Multi-file components match one complete entry; files from different versions are not combined. Source bytes in `snapshots/` are unchanged upstream files and retain their embedded license notices. Entries referencing other `third_party` directories retain those components' existing license and provenance files.

The build verifies every fingerprint and emits a compact component-to-reference table. Startup compares bounded file contents in process, using the existing Zsh file-reading builtins. The installed references are deduplicated by SHA-256. Wsh never executes them. A runtime hashing interface is unnecessary for this initial catalog; the exact reference bytes are also useful for reproducing handoff tests.

## Adding a snapshot

1. Read the source from an immutable upstream Git revision. Verify that the revision is upstream, rather than merely the HEAD of a user's fork. Record its repository, revision and upstream paths.
2. Retain the exact relevant files under `snapshots/SHA256`, or reference an existing vendored copy. Preserve its license. Add the entry and its handoff family to `catalog.json`.
3. Run `python3 build/plugin-catalog.py --check`, then build a development installation.
4. Run `python3 native/test-plugin-catalog.py INSTALLATION OUTPUT`. Every entry receives real interactive startup, customization and ownership checks. Autosuggestion and history entries also exercise the editor. Existing component suites test the current native implementation more deeply.
5. Run the host and canonical floor contracts, retain matched startup measurements and update the accepted evidence verifier. Expand a handoff rule only when a concrete test establishes the need.

Settings remain user-owned. Implementation-function overrides, unsafe active state, unknown source and missing files prevent automatic takeover. Version strings or a clean Git status alone do not establish provenance. No startup network request or automatic plugin update is introduced.

## Autosuggestion lifecycle hooks

Before v0.6.0, upstream excluded all `zle-*` widgets inside its binder. v0.6.0 moved that rule into the configurable ignore list, explicitly allowing users to opt lifecycle widgets in. The handoff for cataloged or Git-recognized older binders therefore adds `zle-*` to the inherited list to preserve its formerly implicit exclusion. Later versions retain the user's list unchanged, including lifecycle opt-ins. The matrix checks both old-version suggestion behavior and an explicitly wrapped `zle-line-init` hook in later versions.

## Local Git fallback

Startup checks the catalog first, including for downloaded files without a Git repository. After a miss, `upstreams.json` identifies supported official repositories, branches and relevant file paths. Wsh verifies a configured official remote, finds the common ancestor of HEAD and its local default-branch tracking reference, and compares the actual files with raw blobs from that one commit. Unrelated local commits are allowed. Relevant edits, including committed edits and edits hidden by index flags, remain external. Multi-file plugins must match the same upstream commit. Linked worktrees and symlinked checkouts are supported.

This uses the local tracking reference as upstream provenance under normal Git fetch behavior. It is not a cryptographic attestation of user-controlled Git metadata. Wsh performs no startup fetch. Missing references, partial clones, missing Git/coreutils commands and timed-out checks leave the external implementation active. Each Git command has a one-second timeout with a 100 ms kill grace, remote configuration output is limited to 64 KiB, at most eight matching remotes are attempted, and each relevant blob is limited to 128 KiB. Git filters, textconv and replacement objects do not supply comparison bytes.

Verified upstream copies use Wsh's current native implementation whenever the existing component handoff can safely run. New upstream features may temporarily be absent from Wsh. That feature lag does not by itself prevent takeover. Runtime overrides, user settings and active-state restrictions retain their existing treatment. Recognition establishes source provenance; component-specific tests establish the handoff behavior.

Run `python3 tests/plugin-git-provenance.py INSTALLATION OUTPUT` for real Git boundary fixtures and `python3 native/test-plugin-catalog.py INSTALLATION OUTPUT --git` for the complete installed fallback matrix. The [Git fallback qualification](../../benchmarks/git-provenance-2026-09-10/report.md) also checks an actual uncataloged upstream release and measures the additional startup cost. Native ownership has no Git verification work on the editor path.

## Daily upstream monitoring

The `Plugin upstream changes` GitHub Actions workflow checks all configured file sets daily at 13:23 UTC and on manual dispatch. It resolves each upstream branch once, reads relevant files at that immutable revision, validates the Git blob identities, and compares complete file sets with the catalog. Unrelated upstream changes pass. New relevant bytes or a check error fail the run. The artifact contains the result, revisions and source bytes for review; the workflow never executes upstream code or updates the catalog automatically.

GitHub's normal Actions notifications deliver the run result. Notification channels and success filtering are account settings; an email rule can also suppress successful runs of this workflow. The workflow starts running after it reaches the default branch. To check locally, run `python3 build/check-plugin-upstreams.py OUTPUT`. Review changed behavior, update the native implementation where useful, and add reviewed snapshots to keep ordinary startup on the faster catalog path.
