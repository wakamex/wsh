# glibc 2.28 portability experiment

The complete phase-one development bundle has a glibc 2.28 floor. It built from source and passed the full floor suite on Rocky Linux 8.10, and no bundled ELF file imported a symbol newer than `GLIBC_2.28`. The same relocated bundle resolved every recorded ELF dependency and passed the interactive PTY lifecycle test on Ubuntu 22.04. Ubuntu 18.04 with glibc 2.27 rejected the exact `wsh-runtime` binary with `GLIBC_2.28 not found`, confirming the lower artifact boundary.

The experiment used the existing floor suite through `./build/build-glibc-2.28-development-bundle.zsh`. That command built signed upstream Zsh 5.9.2 and the Rust workspace inside the pinned Rocky image, assembled and relocated the bundle, then exercised upstream Zsh tests, 21 Rust tests, manifest verification, the shell and runtime entrypoints, a real Git provider request, theme validation, PTY repaint suppression, runtime-crash fallback, shell-exit cleanup, dynamic-library manifest parity, and the maximum imported glibc symbol.

## Result

| Gate | Result |
|---|---|
| Complete bundle builds on the candidate floor | Pass |
| Upstream Zsh suite | Pass |
| Rust workspace suite | 21 passed, 0 failed |
| Relocated manifest verification | Pass |
| Bundled Zsh and required module load | Pass |
| Real Git provider request | Pass |
| Theme validation | Pass |
| Interactive PTY lifecycle | Pass |
| Manifest lists every ELF `DT_NEEDED` soname | Pass |
| Maximum imported glibc symbol | `GLIBC_2.28` |
| Ubuntu 22.04 dependency resolution and PTY cross-check | Pass |
| Exact runtime on Ubuntu 18.04 with glibc 2.27 | Expected loader rejection: `GLIBC_2.28 not found` |

The accepted tested floor and the exact artifact minimum are glibc 2.28. The newest dynamic symbol is the weak `statx@GLIBC_2.28` reference in `wsh-runtime`, but the resulting ELF version requirement still causes the glibc 2.27 loader to reject this binary. A separately linked bundle might target an older glibc because the newest strong import is `GLIBC_2.23` from Zsh's `mathfunc` module, but that candidate would require another complete build and execution experiment. The current compatibility claim covers the Rocky Linux 8.10 floor environment and the Ubuntu 22.04 cross-check; another distribution requires its own execution result because the bundle also depends on the system library sonames recorded below.

## Question and acceptance gate

The Ubuntu 22.04 baseline produced a bundle whose newest imported symbol was `GLIBC_2.35`, but it did not test an older runtime. The cheapest counterfactual was to build and execute the unchanged product in an actively maintained glibc 2.28 environment.

The counterfactual passed only if the complete existing suite passed in that environment, every bundled ELF dependency matched the manifest, and symbol inspection found no import newer than `GLIBC_2.28`. One attempt was allowed because a failure would first require attribution to the compiler, Zsh, Rust, a system library, or the test harness before another intervention.

## Exact inputs

| Input | Identity |
|---|---|
| Product source | `0c1fe78d6f7fb101275b2f2c899d749707c5e3ee`; product implementation unchanged, portability recipe and documentation present as working-tree changes |
| Development manifest and bundle identity | `32dcfd9091ef09e27a2fb039799e32fd4c20ccffc6d5e7a9690dfd6e76fe197c` |
| Target | `x86_64-unknown-linux-gnu` |
| Floor environment | Rocky Linux 8.10, glibc `2.28-251.el8_10.2` |
| Base image | `quay.io/rockylinux/rockylinux@sha256:f5529992e67440c1a4ae7788244d4381c6909159a88eacd95b7523ae47ced82e` |
| Built builder image | `sha256:b7492621785b28dc77f6e3882df35808030bb292ae2da4b9226c18ce217b734a` |
| Container recipe SHA-256 | `bf32bb99bff6dc04111b783603b6d16d39529c6d8724af2b36810e48c40f8c4a` |
| Driver SHA-256 | `53fe05525445ac135de64657592a7531f33b5215abe3da31c944cae34c210614` |
| Floor suite SHA-256 | `6289ee797755c552ac06d7da7b69c812642d0f1864f7d2d7d0ab4562d69d7bee` |
| Zsh | Signed upstream 5.9.2 archive, SHA-256 `36fa734374b44783582cec09bcd67822e2f992c779ec1624ab5596df078d2f81`, no patches |
| Zsh compiler and linker | GCC `8.5.0-28`, GNU ld `2.30-128.el8_10` |
| Rust | `rustc 1.95.0 (59807616e 2026-04-14)`, release profile |
| Cargo lockfile SHA-256 | `981d86851f56371ac454c62ec404a3e1f53890782e33d526252a856700f68248` |
| Ubuntu cross-check environment | Builder from `0c1fe78:build/Containerfile.glibc-2.35`, based on pinned Ubuntu 22.04 image `sha256:34577a83cd7a8f1e55f6eb173fd9bb70c16127a83d6bf06f56f6b1fff9e406b9` |
| Lower-bound environment | Ubuntu 18.04 with glibc `2.27-3ubuntu1.6`, image `docker.io/library/ubuntu@sha256:dca176c9663a7ba4c1f0e710986f5a25e672842963d95b960191e2d9f7185ebe` |

The Rocky package transaction used the repositories attached to the pinned image and was not a frozen repository snapshot. The observed runtime package identities were GCC `8.5.0-28.el8_10`, binutils `2.30-128.el8_10`, libcap `2.48-6.el8_10.1`, ncurses-libs `6.1-10.20180224.el8`, PCRE2 `10.32-3.el8_6`, and Git `2.43.7-1.el8_10`. An official release builder must additionally pin or retain all resolved package inputs as required by the release policy.

## Dynamic-library boundary

The manifest and a fresh `readelf` scan agreed on these required sonames:

```text
ld-linux-x86-64.so.2
libc.so.6
libcap.so.2
libdl.so.2
libgcc_s.so.1
libm.so.6
libncursesw.so.6
libpcre2-8.so.0
libpthread.so.0
librt.so.1
libtinfo.so.6
```

The floor test executed the manager, bundled Zsh, loadable modules, runtime, provider, and interactive adapter in Rocky Linux rather than relying only on this static list. The Ubuntu cross-check then used the exact relocated Rocky-built bundle without rebuilding it.

## Reproduction

```sh
./build/build-glibc-2.28-development-bundle.zsh
```

The command requires Podman and the local pinned Rust toolchain and Cargo cache described by the development build policy. It produces an unsigned development bundle under `build/portable/glibc-2.28/bundles/`.

The lower-bound check used the exact resulting bundle and expected a nonzero exit:

```sh
podman run --rm --userns=keep-id --network=none \
  --volume "$PWD":/workspace:ro,Z \
  docker.io/library/ubuntu@sha256:dca176c9663a7ba4c1f0e710986f5a25e672842963d95b960191e2d9f7185ebe \
  /workspace/build/portable/glibc-2.28/bundles/32dcfd9091ef09e27a2fb039799e32fd4c20ccffc6d5e7a9690dfd6e76fe197c/bin/wsh-runtime \
  validate-theme \
  /workspace/build/portable/glibc-2.28/bundles/32dcfd9091ef09e27a2fb039799e32fd4c20ccffc6d5e7a9690dfd6e76fe197c/share/wsh/themes/minimal.toml
```

The loader printed:

```text
/lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.28' not found
```
