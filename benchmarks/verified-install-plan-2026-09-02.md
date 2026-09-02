# Verified install experiment

## Question

Can `wsh` verify GitHub build provenance once while installing a release, reject identity and content substitution before extraction, and leave the measured shell-launch path unchanged?

## Baseline

Commit `6bae02227e160b8170260ae690278622c4b7bb18` has no install command or native attestation verifier. A local bundle can be fully hashed and atomically activated, but the manager accepts any structurally valid release bundle without proving that GitHub Actions built it from the expected `wakamex/wsh` tag and commit.

The accepted launcher baseline is recorded in [`exec-launch-2026-09-02/report.md`](exec-launch-2026-09-02/report.md): the isolated paired median launcher overhead is 0.70 ms and the glibc 2.28 first-editable manager contribution at p90 is 0.527 ms.

## Cheapest counterfactual

Keep the existing `wsh` launcher binary unchanged and add a separate release-install helper to the same distribution. The helper uses an offline Sigstore bundle supplied with the release, verifies the artifact digest and GitHub identity, extracts only regular files and directories into a private staging directory, verifies the complete wsh bundle, runs fixed smoke tests, moves the immutable bundle into its content-addressed destination, and atomically activates it.

This boundary is smaller than a resident update service and avoids linking certificate, transparency-log, and archive code into every shell launch. Network acquisition remains a later layer because it does not change the verification or installation transaction.

## Fixed gates

The intervention passes only if all of these gates hold:

1. A real external GitHub Actions build-provenance bundle verifies against its exact repository, ref, commit, and signer workflow through the same verifier API used by wsh.
2. A changed artifact digest, wrong source repository, wrong source ref, wrong source commit, wrong signer workflow, malformed attestation, non-release manifest, release/tag mismatch, manifest/commit mismatch, unsafe archive path, link entry, duplicate entry, unlisted payload, or failed smoke test is rejected before activation.
3. Failed extraction or verification leaves the old activation record unchanged and removes the private staging directory.
4. A successful install places exactly one fully verified content-addressed bundle, atomically selects it, and keeps the previous bundle available for offline rollback.
5. Attestation verification performs no network I/O. The release workflow publishes its offline verification bundle beside the artifact.
6. Normal `wsh run` reads no attestation or archive data, makes no update-related network call, and stays within the existing paired-median and first-editable launcher gates of 1.0 ms over the direct bundled-Zsh control.
7. Warm offline provenance verification is at most 250 ms at p90 on the controlled host. Complete local installation is reported separately because archive size, decompression, payload hashing, and smoke tests dominate it.

## External contract fixture

The verifier integration test uses the public `cli/cli` v2.96.0 GitHub Actions SLSA provenance for `gh_2.96.0_linux_amd64.tar.gz`, captured from GitHub's attestation API. Its repository ids, source ref, source commit, workflow path, artifact digest, Rekor proof, Fulcio certificate, SCT, and signed checkpoint are external inputs. The fixture is retained with reproduction metadata and checked against both the native verifier and `gh attestation verify` when the networked differential test is run.

## Attempt limit

Try one verifier/library boundary and one archive/install transaction. If either cannot pass its correctness gate without broad custom cryptography, a resident service, or a second persistent state model, stop and audit the premise before adding machinery.
