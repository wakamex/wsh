# Phase-one direct Git control

The first provider question is how much prompt-transition latency belongs to the equivalent Git scan before wsh adds transport, parsing, snapshot publication, rendering, or repaint work. On the pinned 1,000-file fixture, the direct optional-lock-safe scan added 5.126 ms for clean, 5.578 ms for tracked-dirty, and 7.565 ms for untracked transitions over raw Zsh medians. Each transition used exactly one Git process and none ran without `GIT_OPTIONAL_LOCKS=0`.

The result came from 20 clean, tracked-dirty, and untracked transitions per target through the same PTY harness. The raw summary is retained in [`direct-git-control-2026-09-01.tsv`](direct-git-control-2026-09-01.tsv).

## Reproducer

```sh
cd ../zsh-theme-bench
./research/benchmark-core-themes.zsh --target raw --target direct-git --iterations 20 --fixture-files 1000 --settle-ms 150
```

The benchmark identity was `2a8202573382705a9d423e5818e57d59e774bf3e`, Zsh was 5.9, Git was 2.55.0, the Oh My Zsh fixture identity was `2264a8042763edf2620cfe32d96b096e1f3d26aa`, and the host ran Linux 7.1.9-200.fc44.x86_64. This control intentionally has no prompt semantics or repaint so it is a collection-cost baseline, not a wsh implementation result. It is also not the bundled-Zsh baseline because the first bundle contains Zsh 5.9.2.

## Matched bundled controls required before provider work

The provider comparison must run the same PTY workload through four paths built around the exact Zsh binary identified by the development manifest: bundled Zsh without wsh integration, bundled Zsh with the idle integration and runtime, bundled Zsh with the direct optional-lock-safe Git scan, and the complete provider and renderer. The first two paths measure Zsh itself and the resident service cost before collection. No provider result is accepted until all four outputs share the binary, fixture, transition, instrumentation, and retained-sample rules.

## Provider gate

The cheapest counterfactual is the same one-process scan through the session runtime. It must preserve one Git process per transition, zero calls without optional-lock suppression, and all advertised state semantics. The fixed first milestone thresholds are at most 7.1 ms p90 and 8.0 ms maximum added over raw Zsh for updated Git state. The first clean-revision matched run is retained in [`phase-one-pre-polling.md`](phase-one-pre-polling.md); it passed the other gates but missed the p90 threshold, so it remains an optimization baseline rather than an accepted provider result.

## Development bundle identity

The first exercised unsigned bundle manifest digest was `61728001168e8d7b4497a9028980daa4a535ef6c0e9e4ae74e2d139e49103730`. It used Zsh 5.9.2 built from source archive SHA-256 `36fa734374b44783582cec09bcd67822e2f992c779ec1624ab5596df078d2f81`, verified signer fingerprint `7CA7ECAAF06216B90F894146ACF8146CAE8CBBC4`, Zsh binary SHA-256 `f6047ea62ecb223d9a4cbce7c4fb5230540d5f18089a39829f7f48fb8753df76`, rustc 1.95.0, and GCC 16.2.1. Its source identity ends in `+dirty` because it was a development artifact assembled before a commit; it is not a release provenance claim.
