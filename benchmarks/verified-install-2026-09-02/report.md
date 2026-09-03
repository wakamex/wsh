# Offline provenance verification adds 2.229 ms at p90 and no startup work

The security question was whether checking GitHub build provenance would make installation slow or weaken shell startup. Offline verification took 2.229 ms at p90 across 100 warm samples, while the unchanged launcher stayed below its 1.0 ms gates: 0.80 ms paired median in isolated launches and 0.702 ms p90 contribution through the first editable prompt. Attestation verification runs only before a candidate is extracted and activated.

The verifier used a real public GitHub CLI build-provenance bundle and its exact external repository, ref, commit, signer workflow, Fulcio certificate, SCT, Rekor entry, inclusion proof, checkpoint, and artifact digest. The same artifact, bundle, and identity policy also passed `gh attestation verify`. Transaction tests separately installed release-shaped archives, rejected invalid provenance and link entries before activation, cleaned staging directories, refused an implicit downgrade, allowed an explicit downgrade, and completed an offline rollback.

| Result | Fixed gate | Measured | Status |
| --- | ---: | ---: | --- |
| Warm offline provenance verification p90 | At most 250 ms | 2.229 ms | Pass |
| Warm offline provenance verification median | Report | 1.989 ms | Reported |
| Warm offline provenance verification maximum | Report | 2.448 ms | Reported |
| Isolated paired median launcher overhead | At most 1.0 ms | 0.80 ms | Pass |
| Launcher contribution through first prompt, p90 difference | At most 1.0 ms | 0.702 ms | Pass |
| Complete managed startup added over raw, p90 difference | At most 5.0 ms | 2.518 ms | Pass |
| Network syscalls during non-interactive activated launch | 0 | 0 | Pass |

## Verification and installation boundary

`wsh-install` is a separate Rust executable in the same source and release process as the launcher. It hashes the archive, verifies a supplied offline Sigstore bundle against the fixed `wakamex/wsh` numeric repository identity, exact tag ref, exact source commit, exact `.github/workflows/publish.yml` signer, and exact signer revision, then validates the authenticated artifact name. Its pinned verifier checks the DSSE signature, SLSA provenance subject, Fulcio chain, embedded SCT, Rekor v1 signed entry timestamp, Merkle inclusion proof, signed checkpoint, and certificate identity.

Only after that check does it extract the xz-compressed tar archive into a private directory beneath the installation root. The extractor accepts relative normal paths, one lowercase SHA-256 root, ordinary directories, regular files with mode 0644 or 0755, at most 100,000 entries, at most 512 MiB of compressed input, and at most 1 GiB of declared file content. It rejects links, special files, traversal, absolute paths, duplicate archive paths, multiple roots, special mode bits, and limit violations.

The helper then runs the existing strict manifest and full payload verification, requires release status, matching tag and source commit, a compatible manager version, and the content-addressed directory name, and runs fixed Zsh and runtime smoke tests. It moves the complete bundle to its final digest path and atomically replaces the activation record. Any failure before the final state write leaves the previous selection unchanged. An installed older release also requires `--allow-downgrade`.

Attestation verification is not repeated during startup. `wsh run` continues to read only compact activation state and entrypoint metadata before `exec`. Explicit `bundle verify`, `bundle current`, activation, and rollback still hash installed payloads; rollback does not contact GitHub or reverify the historical attestation.

## Publication integration

The release workflow now grants the artifact-metadata permission required by the pinned attestation action, attests the archive, manifest, launcher, installer, build records, and checksum list, and publishes the resulting offline Sigstore bundle as another immutable release asset. Before publication it verifies every subject with a digest-pinned GitHub CLI 2.96.0 and exact repository, workflow, signer revision, source ref, source revision, and hosted-runner policy. GitHub's release attestation remains the publication-time immutability check; the native installer currently verifies the workflow build provenance carried in the published offline bundle.

The subsequent [release-bootstrap experiment](../bootstrap-install-2026-09-02/report.md) supplies release-specific trusted launcher and installer digests. Downloading an untrusted verifier and asking that same binary to authenticate itself would not add a trust boundary. Later updates can rely on the already-installed verifier.

## Measurement method

The provenance benchmark built the release-optimized helper and reused the same in-memory 13,963-byte public bundle bytes for 100 measured calls after one warmup. Each call reparsed the bundle, reconstructed the embedded trust store and policy, and ran the complete offline cryptographic chain. The raw nanosecond samples are in [`provenance.tsv`](provenance.tsv).

The startup rerun used the new complete glibc 2.28 build, bundle `0643399ec360bf68693bbe32360e5c574c78957726d7bd8702e989baa6c6230a`, and the existing controlled launcher and first-editable methods. The isolated run used ten paired observations of 100 direct or managed starts after warmup. The PTY run used 40 observations per variant around the same clean 1,000-file repository fixture. The distributions are retained in [`launcher.tsv`](launcher.tsv) and [`first-editable.tsv`](first-editable.tsv). A network-only `strace` of activated `wsh run -- -f -c exit` produced the empty [`launch-network.trace`](launch-network.trace).

The complete official install duration cannot be measured before an official wsh archive and matching workflow attestation exist. The result here isolates the added security work that motivated the experiment and shows it is small relative to one-time decompression, payload hashing, and smoke tests. The real release install remains a required end-to-end measurement.

## Exact identities

The tested floor launcher SHA-256 was `67ab173d27e9e948889b27651a406c6d5b2eaa6b20bb271beea20ff1902f2997`, the separate installer SHA-256 was `9b3cb57f753d30ad9d08c277de2df6263ab2a4ae8196c61b4d150a51149f1104`, the canonical development archive SHA-256 was `e17c363c290fd2b1d11794d50bbc32e36576b457705ee8003a48b5cb7ebcd4af`, and the bundled Zsh SHA-256 remained `bac80fcae8e1dd2aa1d5b77d5a68a7bb73612f8bf349d1f33e775117b7cd5cfb`. [`metadata.txt`](metadata.txt) records the remaining source, dependency, fixture, build, benchmark, and host identities.

The fixed hypothesis, gates, external fixture, and one-attempt limit were recorded before implementation in [`../verified-install-plan-2026-09-02.md`](../verified-install-plan-2026-09-02.md).
