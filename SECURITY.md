# wsh theme and update trust model

`wsh` reduces the authority attached to appearance and updates. A theme is a non-executable definition rendered by trusted prompt components, and a shell startup never downloads or modifies installed code. Native updates use the system package manager; official artifacts carry GitHub build provenance and reproducibility evidence.

These guarantees cover `wsh` theme definitions and the native packaged installation. User Zsh configuration, selected plugins, compatibility adapters, and programs launched from the shell remain executable code with the user's normal authority. Bundled editing defaults are trusted executable bundle components rather than theme definitions; their exact sources and digests follow the complete release review, testing, signing, and rollback path. History substring search is the first accepted component under this policy.

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

## Native package authenticity and updates

A native package contains the pinned Zsh executable, linked modules, C helper, trusted integration and data-only themes. Its manifest covers every payload file and records source, SDK, compiler and system-library identities. Two isolated release builds must produce identical RPM and manifest bytes. GitHub build provenance binds the official artifacts to the authorized source and workflow. Bare checksums provide integrity, not publisher authentication; the RPM currently has no separate maintainer GPG signature.

System packages own complete installation, upgrade and downgrade transactions. Wsh performs no startup update check and has no native bootstrap installer or activation record. Installing a local development RPM is an explicit administrative action and does not turn it into an official release. The [release contract](RELEASES.md) defines artifact verification and publication.

Account login starts a system-owned shell without private bundle state. Ordinary RPM removal refuses while local accounts name the registered shell paths. Missing system binaries or required libraries, remote identity directories, arbitrary aliases and scriptlet bypass still require administrator management. The [installation guide](NATIVE-INSTALLATION.md) defines these boundaries and the separate-login test before changing an account shell.

## Security properties have regression tests

The theme tests submit definitions and provider values containing command substitutions, parameter expansions, prompt escapes, control characters, OSC sequences, malformed encodings, oversized values, excessive segments, unknown operations, recursive references, and crafted Git branch names. Validation must reject unsafe definitions, and rendering must preserve intended text without executing it or emitting unintended terminal controls.

Startup tracing must show zero update-related network calls and writes. Theme loading and rendering are compared with the same prompt components and provider requirements but no theme definition; loading may read the selected definition itself, but the definition cannot trigger another file read, child process, or network access. Parsing, validation, rendering, and output bounds are benchmarked so non-executability does not hide an unbounded resource path.

The update tests tamper with manifests and artifacts, substitute GitHub repository, ref, commit, and workflow identities, submit malformed attestations and unsafe archives, change the bootstrap's downloaded launcher and installer, withhold a bootstrap asset, replace older regular native tools, present symbolic-link and non-regular tool destinations, substitute individual Zsh and runtime files across otherwise valid releases, replay older releases, interrupt installation before activation, fail candidate smoke tests, keep an old session running during activation, start a new session after activation, make the active Zsh and runtime unstartable, and perform a manager-side offline rollback. Release validation also repeats the clean build and compares the unsigned bundle, release tools, and bootstrap byte-for-byte. Cases not yet automated remain release blockers rather than implied coverage.

## The boundary does not sandbox Zsh

Users can still source arbitrary Zsh code, install executable plugins, invoke programs, or replace trusted prompt components. `wsh doctor trust` should identify the active runtime and theme digests, signing identity, reproducibility record, update channel, executable plugins and adapters, local overrides, and anything outside the verified distribution. It reports authority rather than claiming to sandbox code that the user deliberately loaded.

A non-executable definition can intentionally draw misleading words or icons, just as any visual theme can. The contract prevents shell execution, untrusted-data expansion, and raw terminal control; it does not certify a third-party design as honest or useful. Preview, provenance, directory reporting, and separate recommendation are the appropriate controls for presentation abuse.

## Native package trust and availability

The native development package relies on the system package manager for file ownership, installation and transactions. Its account-shell executable starts independently of user activation records and optional prompt resources. Bundled modules live in that executable; external modules retain their Zsh ABI contract. Theme parsing and rendering use the qualified C helper with the existing non-executable schema and bounds. The current local RPM and builder extension are unsigned development artifacts. They do not inherit the legacy GitHub attestation/update contract automatically. Native package signing, publication and repository trust require a separate approved release contract. [Installation and recovery](NATIVE-INSTALLATION.md) describes the tested account-shell and removal boundaries.
