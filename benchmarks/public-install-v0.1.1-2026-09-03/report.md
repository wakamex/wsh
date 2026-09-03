# Public v0.1.1 installation reaches an editable prompt in 1.757 seconds at p90

The public-install question was whether downloading, authenticating, extracting, verifying, activating, and starting the complete wsh bundle would make first use feel slow. Ten fresh installations passed in each tested environment. Fedora 44 reached an editable prompt in 1,756.501 ms at p90, and the glibc 2.28 Rocky 8.10 environment reached one in 1,115.246 ms. Both passed the fixed 5-second total gate, while the installed shell itself reached its first prompt in under 10 ms at p90.

The harness used the documented immutable GitHub Release URL and real HTTPS for the bootstrap and all four downloaded assets. Every observation began with new home, binary, libexec, install, and activation directories, required the exact `v0.1.1` release and source commit, and ended only after the installed launcher produced an editable prompt under a PTY.

| Environment and stage | Median | p90 | Maximum | Fixed gate | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| Fedora 44 complete download-to-prompt path | 1,666.643 ms | 1,756.501 ms | 2,028.953 ms | p90 at most 5,000 ms | Pass |
| Fedora 44 bootstrap download | 104.160 ms | 126.642 ms | 166.363 ms | Report | Reported |
| Fedora 44 bootstrap execution and full installation | 1,555.291 ms | 1,636.134 ms | 1,853.750 ms | Report | Reported |
| Fedora 44 installed first prompt | 8.883 ms | 9.130 ms | 9.142 ms | p90 at most 50 ms | Pass |
| Rocky 8.10 with glibc 2.28 complete download-to-prompt path | 1,098.486 ms | 1,115.246 ms | 1,149.717 ms | p90 at most 5,000 ms | Pass |
| Rocky 8.10 with glibc 2.28 bootstrap download | 117.127 ms | 133.203 ms | 138.553 ms | Report | Reported |
| Rocky 8.10 with glibc 2.28 bootstrap execution and full installation | 963.429 ms | 1,001.962 ms | 1,035.045 ms | Report | Reported |
| Rocky 8.10 with glibc 2.28 installed first prompt | 8.244 ms | 8.446 ms | 8.492 ms | p90 at most 50 ms | Pass |

## v0.1.0 failed before activation

The first published `v0.1.0` bundle exposed a missing release-path test: its installer invoked the candidate Zsh with `-f`, bypassing the relocatable `.zshenv`, so `zsh/datetime` remained tied to the build prefix. Installation stopped before activation. The [retained failure](../public-install-v0.1.0-failure-2026-09-03.md) records its output and cause.

The `v0.1.1` installer uses the same `-d`, `WSH_BUNDLE_ROOT`, and bundled `ZDOTDIR` contract as normal launch. Its fixture rejects missing relocation state or different flags, and the compatibility-floor suite now loads `zsh/datetime` directly from a relocated bundle before testing manager launch. GitHub's immutable-release policy left `v0.1.0` unchanged and required the correction to use a new release.

## Measurement method

Each environment received one unmeasured correctness run followed by 10 measured fresh installations. Timing begins immediately before downloading `wsh-v0.1.1-install.sh`. Bootstrap execution includes four real GitHub HTTPS downloads, native-tool digest verification, offline GitHub Actions provenance verification, safe extraction, manifest and payload verification, candidate smoke tests, and atomic activation. The prompt interval begins immediately afterward and launches the installed `wsh` under a PTY. Container startup is excluded from the Rocky result.

The exact documented `curl | sh` command also passed once in fresh isolated state in each environment. Both installations selected manifest `9ec9ecf5226a39220b96f8a3e1522229b5ffea0ebc7bbd3909465500dd6e373e`, reported `v0.1.1` and source commit `e62e19fe1cf8b10d28b703e2670b6478e540f38d`, and loaded `zsh/datetime` through the installed launcher.

The Fedora observation used glibc 2.43. The Rocky container used its pinned 8.10 package set and glibc 2.28 while sharing the host kernel and network. The comparison does not claim that Rocky is intrinsically faster; GitHub delivery and filesystem conditions varied during the two sequential runs. Raw observations are in [`fedora.tsv`](fedora.tsv) and [`rocky.tsv`](rocky.tsv).

## Exact release identity

The measured release is [`v0.1.1`](https://github.com/wakamex/wsh/releases/tag/v0.1.1) from source commit `e62e19fe1cf8b10d28b703e2670b6478e540f38d`. Its [eligibility run](https://github.com/wakamex/wsh/actions/runs/33707623225) passed before the annotated tag was pushed. Its [publication run](https://github.com/wakamex/wsh/actions/runs/33708035426) produced two matching canonical builds, attested every staged asset, published the immutable release, and verified the release and each asset. [`metadata.txt`](metadata.txt) records the environment, commands, artifact digests, and input hashes. The fixed gates and sample rule are in [`../public-install-v0.1.1-plan-2026-09-03.md`](../public-install-v0.1.1-plan-2026-09-03.md).
