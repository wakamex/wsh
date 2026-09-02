# Official release and local build policy

Only an immutable GitHub Release in `wakamex/wsh` is an official `wsh` release. Every bundle produced by a local checkout, pull request, ordinary branch workflow, or manual build remains a development bundle. A local build can reproduce and verify an official asset byte-for-byte, but matching bytes do not make the local copy an independently published official release.

## One release publishes complete target bundles

Each release asset is one canonical archive containing the exact Zsh binary and modules, matching `wsh` runtime, integration adapter, schemas, and bundled theme definitions for one target. Individual files are never release assets that the manager can mix into an installed bundle. Changing Zsh, Rust code, a trusted adapter, a schema, a theme, the compiler, a linked dependency, or build flags creates a new complete candidate and reruns every gate.

The first target is `x86_64-unknown-linux-gnu` with glibc 2.35 as its compatibility floor. Ubuntu 22.04 provides this build and test environment and remains in standard maintenance through May 2027 according to [Canonical's release cycle](https://ubuntu.com/about/release-cycle?product=ubuntu&release=ubuntu&version=22.04+LTS). Moving the floor or builder image requires a recorded compatibility reason and a complete rerun.

## Reproducibility compares two isolated builds

The release workflow starts twice from the same pinned source commit, upstream Zsh archive and signature, dependency lockfile, Rust toolchain, target, builder image digest, build recipe, environment, locale, timezone, archive ordering, timestamps, ownership, and compression parameters. The jobs use separate clean workers and do not exchange build directories or compiler caches. Each job emits the canonical archive digest, bundle manifest digest, file table, toolchain identities, test results, and build log.

Publication is blocked unless the two canonical archives match byte-for-byte. Agreement detects undeclared state and nondeterminism between those executions. It does not establish two independent trust domains when both jobs run on GitHub infrastructure. A later second-provider builder is justified if the project wants that stronger claim.

The agreed archive and manifest are subject to GitHub build-provenance attestations tied to the release workflow, repository, commit, and artifact digest. The project also publishes the two build records so a third party can rerun the same recipe. GitHub documents both [artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations) and [offline attestation verification](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations).

## GitHub publication supplies the official signature and immutability boundary

The release is assembled as a draft after the tag commit passes correctness, performance, portability, reproducibility, and rollback gates. The publisher attaches only the agreed assets and their build records, verifies their digests, and publishes the draft with GitHub release immutability enabled.

GitHub immutable releases lock the tag and assets and automatically produce a signed release attestation covering the tag, commit, and assets. GitHub documents these properties in [Immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases) and exposes release and local-asset verification through `gh release verify` and `gh release verify-asset` in [Verifying the integrity of a release](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/verify-release-integrity).

The first updater should trust the fixed `wakamex/wsh` repository identity, require the immutable release attestation, require the expected release-workflow build attestation for every downloaded asset, verify the bundle manifest and every installed file, and reject an older version unless the user explicitly requests a downgrade. It must fail closed if the required GitHub verification material is unavailable or invalid. A custom project signing hierarchy is deferred unless implementing GitHub attestation verification inside the manager proves impractical or a non-GitHub release channel creates a concrete need.

## Activation and rollback remain local atomic operations

Download and verification happen in a new content-addressed directory. After the candidate passes a no-side-effect launch check, one atomically replaced state record selects the new complete bundle and retains the previous selection. An interrupted write leaves the old state record intact. Rollback verifies and selects the previous bundle without starting or trusting the broken active Zsh or runtime.

The manager never mutates an installed bundle and never updates one component within it. It performs no update check during shell startup. Checking, downloading, and activating are separate explicit commands, and a downloaded candidate is inert until activation succeeds.

## Release gates

An official GitHub Release requires all of the following:

1. The exact source commit and tag are fixed.
2. The signed upstream Zsh archive, dependency lockfile, toolchain, builder image, and build recipe are pinned.
3. Rust tests, Zsh upstream tests, theme-schema tests, provider fixtures, adversarial protocol tests, PTY lifecycle tests, tamper tests, and rollback tests pass.
4. The complete bundle runs on the documented glibc floor.
5. The retained benchmark passes semantic, process-count, optional-lock, repaint, first-editable, settled-latency, tracing-overhead, and memory gates.
6. Two isolated canonical builds produce the same bytes.
7. Build-provenance attestations cover the agreed assets and workflow identity.
8. A draft release contains the complete asset set and build records before it becomes immutable.
9. Release and asset verification succeeds after publication.

Until all nine gates exist and pass, the repository can publish source and development artifacts but has no official binary release.
