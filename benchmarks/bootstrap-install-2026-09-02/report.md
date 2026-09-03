# Release bootstrap orchestration completes in 61.642 ms at p90

The first-install question was whether wsh could offer one straightforward command without letting a downloaded verifier authenticate itself or adding network work to shell startup. The release-specific bootstrap passed its substitution and failure gates, and 30 warm local-file runs completed in 61.642 ms at p90. The production script downloads four exact immutable-release assets; network transfer and the full archive installation remain separate costs.

The test rendered the script twice, exercised a successful first install and exact rerun, and then changed each native tool, removed the archive, supplied a conflicting existing tool, supplied a symbolic-link destination, reported an unsupported platform, and reported glibc 2.27. Each invalid case stopped before executing the candidate installer or creating activation state. The existing native external-attestation test remains responsible for authenticating the downloaded archive.

| Result | Fixed gate | Measured | Status |
| --- | ---: | ---: | --- |
| Local bootstrap orchestration p90 | At most 100 ms | 61.642 ms | Pass |
| Local bootstrap orchestration median | Report | 60.298 ms | Reported |
| Local bootstrap orchestration maximum | Report | 63.932 ms | Reported |
| Deterministic render | Byte-identical | 2/2 identical | Pass |
| Valid first install and exact rerun | Both succeed | 2/2 | Pass |
| Changed installer and launcher | Reject before execution | 2/2 | Pass |
| Missing archive | Reject before tool installation | 1/1 | Pass |
| Conflicting file and symbolic-link destination | Reject without replacement | 2/2 | Pass |
| Unsupported platform or glibc 2.27 | Reject before download | 2/2 | Pass |

## Bootstrap trust boundary

The release workflow renders a deterministic POSIX shell script after two isolated builders agree on the archive, launcher, and installer bytes. The script embeds the exact release tag, source commit, asset names, immutable GitHub Release base URL, and SHA-256 digests of both native tools. The two generated scripts must also match byte-for-byte.

At first install, the script requires Linux x86-64, glibc 2.28 or newer, and the ordinary host `curl`, `sha256sum`, `install`, and filesystem tools. It downloads the exact archive, offline provenance bundle, launcher, and installer into a private temporary directory. Both native digests must match before either binary is executed or placed in its final path. Existing tool paths are accepted only when they are ordinary files with the exact expected digest. The authenticated installer then verifies the archive's GitHub build provenance, manifest, complete payload, release identity, source commit, manager compatibility, and smoke tests before activation.

Network acquisition stays in this script because the host HTTPS client is already required to obtain the first trusted native executable. A second HTTP and TLS implementation inside `wsh-install` would not remove that bootstrap trust and would enlarge the native verifier dependency graph. Later updates can use the already installed verifier and require a separate experiment.

The bootstrap script is itself included in the two-build byte comparison, release checksum list, and GitHub build-provenance attestation. The downloaded provenance bundle authenticates the archive independently of the script's embedded native-tool hashes. GitHub release immutability remains the publication boundary.

## Measurement method

The benchmark used the production rendering and bootstrap logic with real `curl`, `sha256sum`, `install`, `mktemp`, and filesystem operations. Exact `file://` release URLs removed network variability, and a strict fixture installer rejected any unexpected tag, commit, asset name, flag, or argument count. Each of 30 measured runs used fresh tool directories and included four curl process invocations, both digest checks, directory and atomic-file work, and candidate-installer execution. Raw nanosecond samples are retained in [`samples.tsv`](samples.tsv).

This result measures the new orchestration rather than claiming a complete release-install duration. The first official release must add the real HTTPS transfer, archive decompression, full payload hashing, native provenance check, and Zsh and runtime smoke tests to an end-to-end measurement. Ordinary `wsh run` is unchanged and continues to use only compact activation state with no network call.

## Exact identities

The baseline source revision was `424d7314a03227355fc08be2d149d4a7430909d8`, the accepted implementation and evidence revision was `8e1dd0018d06f9f01a7d7b44ae449cafa7e03f00`, and the publication-workflow provenance refresh was `e253573211e0d6a9d2943f943ff04ae1d21f6dd9`. [`metadata.txt`](metadata.txt) records those revisions, implementation and sample digests, command, host, and CPU. The verifier reads the pinned historical Git objects so later bootstrap changes do not rewrite the accepted result's implementation identity. The fixed hypothesis and gates were recorded before implementation in [`../bootstrap-install-plan-2026-09-02.md`](../bootstrap-install-plan-2026-09-02.md).
