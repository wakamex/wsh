# Release-specific bootstrap experiment

## Question

Can a first-time user install an exact wsh release with one release-specific script while preventing a downloaded installer from authenticating itself, keeping failed downloads and substitutions inert, and leaving shell startup unchanged?

## Baseline

Commit `424d7314a03227355fc08be2d149d4a7430909d8` publishes a reproducible launcher and installer design and implements offline release installation, but it has no network acquisition or trusted first-install path. A user would have to download four assets, independently obtain the expected installer and launcher digests, and invoke `wsh-install` with the exact tag and commit.

## Cheapest counterfactual

Generate one deterministic POSIX shell script for each release after the two builders agree. The script embeds the exact tag, commit, asset names, installer digest, and launcher digest. It downloads only those immutable GitHub Release URLs into a private temporary directory, verifies both release-tool digests before executing or installing either tool, installs those tools only when their destinations are absent or already byte-identical, and passes the downloaded archive and offline provenance bundle to the existing `wsh-install` transaction.

The bootstrap owns network acquisition because it already depends on the host's HTTPS client to fetch its first trusted native executable. Adding an HTTP and TLS stack to `wsh-install` would enlarge the trusted native dependency graph without removing that initial trust step. Later updates can reuse the installed verifier and should get a separate measured design.

## Fixed gates

1. Rendering the same validated release inputs twice produces byte-identical scripts.
2. The script uses exact release-specific asset URLs and verifies the embedded SHA-256 digests of both native tools before executing or installing either one.
3. A changed installer, changed launcher, missing asset, unsupported platform, symbolic-link tool destination, or conflicting existing tool fails without executing the candidate installer, changing the existing tool, or creating activation state.
4. A valid first install places the exact launcher and installer at their documented paths, invokes the authenticated install transaction with the exact tag and commit, and is safely rerunnable when those files already match.
5. Downloads occur only during the explicit bootstrap. Normal `wsh run` remains unchanged and makes zero network syscalls.
6. Across 30 warm local-file runs, bootstrap orchestration through the candidate installer's completion has p90 latency at most 100 ms. Network transfer time and the real archive installation transaction are reported separately because they depend on release size and network conditions.
7. The generated script and every asset it downloads are included in the release checksum list and workflow build-provenance attestation before publication.

## Test boundary

The bootstrap test uses the real `curl`, `sha256sum`, `install`, and filesystem operations against `file://` URLs baked into a test rendering. A strict fixture installer rejects unexpected arguments and records execution only after both tool digests pass. The production rendering accepts only the fixed HTTPS GitHub Release base URL. The existing external-attestation test remains responsible for the native installer's GitHub and Sigstore contract.

## Attempt limit

Try one generated-script boundary without a native network stack or persistent update metadata. If it cannot pass the fixed atomicity and substitution gates, stop and redesign the bootstrap rather than adding recovery state to the interactive launcher.
