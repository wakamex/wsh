# Explicit updates add no material shell-startup cost

The new `wsh update`, `wsh update --check`, and `wsh update --to vMAJOR.MINOR.PATCH` commands make updates discoverable without adding network work to shell startup. The floor-built launcher reached the first editable prompt in 8.016 ms at p90, 0.623 ms over direct complete integration and 2.928 ms over raw bundled Zsh. Both existing startup gates passed.

The CLI correctness test began from a real isolated `v0.1.1` installation. A strict transport fixture verified no-side-effect checks, exact release selection, latest release selection, same-version no-ops, pre-download downgrade and malformed-tag rejection, exact URL construction, private temporary-directory cleanup, state-root forwarding, download failure, and bootstrap failure. A final no-side-effect request passed against GitHub's live latest-release redirect.

| Bundle and path | Median | p90 | Maximum |
|---|---:|---:|---:|
| Raw bundled Zsh | 4.930 ms | 5.087 ms | 5.173 ms |
| Direct complete integration | 7.198 ms | 7.393 ms | 7.766 ms |
| Managed complete startup | 7.810 ms | 8.016 ms | 8.318 ms |

| Fixed gate | Result | Status |
|---|---:|---:|
| Managed p90 added over raw at most 5.0 ms | 2.928 ms | Pass |
| Managed maximum added over raw at most 8.0 ms | 3.145 ms | Pass |
| Manager p90 added over direct complete at most 1.0 ms | 0.623 ms | Pass |

The canonical launcher grew from 868,808 bytes in published `v0.1.2` to 913,768 bytes with the update commands, an increase of 44,960 bytes. The paired raw, direct, and managed measurements show that the added code did not cause a material startup regression at the fixed gates.

## Update behavior

`wsh update --check` follows GitHub's public latest-release redirect, accepts only the exact `https://github.com/wakamex/wsh/releases/tag/vMAJOR.MINOR.PATCH` shape, and reports the comparison without downloading a bootstrap. `wsh update --to` accepts one canonical stable tag and constructs the matching release asset URL directly. Bare `wsh update` performs the same latest lookup and downloads the bootstrap only when that release is newer than the active verified release bundle.

The bootstrap is downloaded through the host `curl` into a newly created mode-0700 temporary directory and executed from a file rather than a network pipe. Success, download failure, and bootstrap failure remove the directory. The release bootstrap remains responsible for native-tool digests, archive provenance, complete payload verification, installation, and activation. Update discovery adds no new installer, HTTP library, resident process, startup hook, or release protocol.

## Measurement method

The complete development bundle was built at source revision `3db37e69cb19546cafd60ae06f8a79fe0da0b89a` in the pinned Rocky Linux 8.10 glibc 2.28 builder. The benchmark used the same 1,000-file Git fixture, five warmups per variant, 40 retained samples per path, alternating forward and reverse order, CPU 31 affinity, and Zsh `zpty` clock used by the accepted startup result. Raw Zsh, direct complete integration, and managed startup used the same bundle and instrumentation.

[`startup.tsv`](startup.tsv) contains every retained sample. [`metadata.txt`](metadata.txt) records the exact source, bundle, binaries, toolchains, builder, workload, command, input hashes, host, and CPU. The fixed behavior and unchanged performance gates were recorded in [`../update-cli-plan-2026-09-03.md`](../update-cli-plan-2026-09-03.md).

The timing result covers shell startup on Fedora 44 using artifacts built at the glibc 2.28 floor. It does not measure release discovery or installation latency, which are deliberate network operations outside startup.
