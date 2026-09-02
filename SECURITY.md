# wsh theme and update trust model

`wsh` reduces the authority attached to appearance and updates. A theme is a non-executable definition rendered by trusted prompt components, and a shell startup never downloads or modifies installed code. Official `wsh` updates are explicit, signed, reproducible, atomic, and reversible.

These guarantees cover `wsh` theme definitions and `wsh`-managed installations. User Zsh configuration, selected plugins, compatibility adapters, and programs launched from the shell remain executable code with the user's normal authority.

## Theme definitions cannot execute shell code

Oh My Zsh currently loads a selected theme by sourcing its `.zsh-theme` file, including files from the custom theme directory. Appearance code therefore runs with the same permissions as the interactive shell. Its 2026 [prompt-injection advisory](https://github.com/ohmyzsh/ohmyzsh/security/advisories/GHSA-x96c-8w82-wf96) also documents ten themes that bypassed a shared escaping fix through separate Git paths. These are concrete failure modes for the `wsh` theme contract to eliminate rather than a general claim that another framework is insecure.

A `wsh` theme definition can select trusted prompt components, arrange them, provide bounded literal text and icons, select named styles, choose among declared variants, and request typed provider fields. It cannot define functions, execute commands, register hooks, read files or environment variables, access the network, load native code, perform command or parameter substitution, include another file recursively, or emit raw Zsh prompt escapes, ANSI controls, or OSC sequences.

The runtime treats provider values such as branch names, paths, hostnames, and command status as untrusted typed data. Prompt components encode those values for their destination and the renderer alone emits terminal controls. Theme literals pass the same control-character validation. Explicit prompt components represent line breaks, styles, hyperlinks, and other terminal behavior so a definition never needs raw escape access.

The schema places limits on definition bytes, segment count, literal and rendered output size, conditional depth, provider requirements, and render time. Unknown schema operations fail validation. A definition cannot introduce a process, file, network, or terminal-protocol capability that its selected prompt components do not already have.

Trusted prompt components are executable `wsh` runtime code. Adding or changing one follows the normal source review, benchmark, release-signing, and update process rather than the theme-directory path.

## Valid themes receive automatic directory admission

The public theme directory uses open submission and mechanical admission. Anyone can publish a theme, and every submitted version is listed when it passes the versioned schema validator, uses only supported prompt components and bounded values, establishes control of its publisher namespace, supplies the required identity and license metadata, and contains no executable or unvalidated files. Maintainers do not reject a valid theme because of its visual style, similarity to another theme, popularity, feature choices, or performance preference.

Directory admission is not the same as bundling, recommendation, or endorsement. Those views can be curated separately without making curation a condition of publication. Search and ranking do not affect whether a valid theme remains installable.

Administrative rejection or removal is limited to failed mechanical validation, namespace conflict or impersonation, unlawful or abusive content, and abuse of the directory service. A removed but schema-valid definition can still be installed directly by content digest. The local validator applies the same execution and terminal-safety rules regardless of where the definition came from.

Each listed version is immutable and identified by its definition digest, schema version, publisher namespace, and source location. The directory publishes a signed snapshot mapping those identities to exact digests. Installation records the selected version and digest. Theme updates are explicit and cannot silently replace an installed definition with changed content under the same version.

The directory runs a standard adversarial corpus and records requested provider fields and measured render cost for each version. These results inform users but do not become subjective admission gates. Hard resource and safety limits remain mechanical validation requirements.

## Release bundles are indivisible

An official wsh release bundle contains one exact Zsh binary and module set for its target, the matching wsh runtime, trusted prompt components and providers, schemas, bundled definitions and adapters, and a manifest covering every payload file. The release records the Zsh source revision and every common or target-specific patch plus each target's build configuration, toolchain, and binary digests.

Every wsh release maps to exactly one recorded Zsh build identity per target. More than one wsh release may reuse the same identity, but a Zsh revision, patch, configuration, or binary change always creates a new complete wsh release. No command updates only Zsh, only the runtime, or another trusted component inside an installed bundle.

Release directories are immutable after verification. Activation selects a complete directory, and rollback selects the previous complete directory. Configuration, locally installed theme definitions, history, caches, and traces remain outside those directories and are not replaced by bundle activation.

The minimal manager and launcher remain outside the selected bundle so listing, verification, selection, and rollback do not depend on the active Zsh or runtime starting successfully. Bundle updates do not replace that manager as a side effect. Its standalone update is a separate signed operation, and an external package manager retains authority over manager installations it owns.

## Official updates are explicit, signed, reproducible, atomic, and reversible

Oh My Zsh runs its [update check during initialization](https://github.com/ohmyzsh/ohmyzsh/blob/master/tools/check_for_upgrade.sh). Its documented default asks before applying an available update, and users can select automatic, reminder, experimental background, or disabled modes. The `wsh` distinction is narrower and testable: interactive startup does no update network or mutation work, and installation requires a separate explicit command.

Starting `wsh` performs no update-related network request and does not mutate the installed shell or runtime. `wsh update check` explicitly retrieves metadata, and `wsh update apply` explicitly installs a selected release. A user may separately enable an operating-system scheduler to check for updates, but that policy is not activated by the interactive shell. A cached local notice can be displayed without network access.

Every official release is an immutable GitHub Release in `wakamex/wsh`. Its signed release attestation covers the tag, commit, and assets, and each platform archive also carries build provenance tied to the expected repository, commit, and release workflow. The authenticated manifest covers every payload-file digest and determines the bundle identity. The updater rejects an invalid repository or workflow identity, mutable or unattested releases, mismatched hashes, component substitution, and an older release presented as an update unless the user explicitly requests a downgrade. [`RELEASES.md`](RELEASES.md) fixes the publication and verification contract. A custom project signing hierarchy remains deferred unless GitHub attestation verification proves unsuitable or another release channel is admitted.

Signing authenticates the published bytes but does not prove how they were built. Before publication, each official unsigned platform payload is built twice in isolated clean workers from the same pinned source, dependencies, toolchain, and build recipe. The payloads must match byte-for-byte. The project publishes the build recipe, input identities, resulting digest, and build provenance so another party can reproduce the comparison. A target that cannot pass this gate is labeled non-reproducible and is not presented as an official reproducible build.

The updater verifies the immutable release attestation, expected build attestation, authenticated manifest digest, and installed-file digests before unpacking into a new immutable version directory. Release payloads cannot supply installer, activation, or migration hooks; the manager owns the fixed installation procedure. It runs the candidate smoke tests before atomically changing the active bundle. Existing sessions continue using their original bundle, and new sessions use the newly active bundle.

The previously active verified bundle remains locally available. `wsh rollback` can reactivate it through the manager without network access or a working active shell. An update does not irreversibly rewrite user configuration as part of activation. If a future configuration migration is necessary, it requires a separate previewable action and a restorable backup. Rolling back to a release with a known security issue can warn, but remains an explicit user decision rather than being disguised as an update.

When `wsh` is installed through an operating-system package manager, that package manager owns download, signature, activation, and rollback behavior. `wsh` still reports its complete build and source provenance, but does not claim that the external channel satisfies the `wsh`-managed update contract.

## Security properties have regression tests

The theme tests submit definitions and provider values containing command substitutions, parameter expansions, prompt escapes, control characters, OSC sequences, malformed encodings, oversized values, excessive segments, unknown operations, recursive references, and crafted Git branch names. Validation must reject unsafe definitions, and rendering must preserve intended text without executing it or emitting unintended terminal controls.

Startup tracing must show zero update-related network calls and writes. Theme loading and rendering are compared with the same prompt components and provider requirements but no theme definition; loading may read the selected definition itself, but the definition cannot trigger another file read, child process, or network access. Parsing, validation, rendering, and output bounds are benchmarked so non-executability does not hide an unbounded resource path.

The update tests tamper with manifests and artifacts, substitute individual Zsh and runtime files across otherwise valid releases, replay old metadata, expire metadata, interrupt every installation phase, fail candidate smoke tests, keep an old session running during activation, start a new session after activation, make the active Zsh and runtime unstartable, and perform a manager-side offline rollback. Release validation also repeats the clean build and compares the unsigned bundle byte-for-byte.

## The boundary does not sandbox Zsh

Users can still source arbitrary Zsh code, install executable plugins, invoke programs, or replace trusted prompt components. `wsh doctor trust` should identify the active runtime and theme digests, signing identity, reproducibility record, update channel, executable plugins and adapters, local overrides, and anything outside the verified distribution. It reports authority rather than claiming to sandbox code that the user deliberately loaded.

A non-executable definition can intentionally draw misleading words or icons, just as any visual theme can. The contract prevents shell execution, untrusted-data expansion, and raw terminal control; it does not certify a third-party design as honest or useful. Preview, provenance, directory reporting, and separate recommendation are the appropriate controls for presentation abuse.
