# Two isolated local builds produced byte-identical archives

Two clean builds of source revision `947d8122254494d4c3f5d8ea9855a56d21d90e1a` produced byte-identical bundle manifests and canonical archives. The shared archive SHA-256 was `5b679a0d99867ee38af7acd8bdd3c9cfe75a3612d555aeaeb5c9f3282811c447`, and the shared manifest and bundle identity was `894fb43d32fab167108fbf35607670af15fa73d2ea92760aba7741c03b26e118`.

The test created two detached Git worktrees and ran the complete glibc 2.28 builder sequentially. Each worker had a separate source tree, Cargo home, Cargo target directory, Zsh output directory, bundle directory, and container build context. Both workers rebuilt Zsh and the Rust workspace, ran the upstream Zsh suite and 21 Rust tests, verified a relocated bundle, served a real Git provider request, passed the PTY repaint, crash, and cleanup checks, reproduced the dynamic-library manifest, and imported no glibc symbol newer than `GLIBC_2.28`. Each canonical archive was extracted and verified before comparison.

| Output | Worker A | Worker B |
| --- | --- | --- |
| Canonical archive SHA-256 | `5b679a0d99867ee38af7acd8bdd3c9cfe75a3612d555aeaeb5c9f3282811c447` | `5b679a0d99867ee38af7acd8bdd3c9cfe75a3612d555aeaeb5c9f3282811c447` |
| Manifest SHA-256 | `894fb43d32fab167108fbf35607670af15fa73d2ea92760aba7741c03b26e118` | `894fb43d32fab167108fbf35607670af15fa73d2ea92760aba7741c03b26e118` |
| Archive size | 2,389,156 bytes | 2,389,156 bytes |
| Complete floor suite | Pass | Pass |

## Pinned inputs

The base image was `quay.io/rockylinux/rockylinux@sha256:f5529992e67440c1a4ae7788244d4381c6909159a88eacd95b7523ae47ced82e`. The complete Rocky RPM lock SHA-256 was `dd63e7520e8c4595c80764a9637d5a09f202b4ed1da6a81e8dee92f21fd5c143`; each of its 231 records includes NEVRA, architecture, RPM header SHA-256, payload digest algorithm, and payload digest.

The Rust lock file SHA-256 was `edb793975309825c42eefadd6f74c1c0a8baba1b947c4e2de5ebdb06f3faeb36`. It selected Rust 1.95.0 and the verified toolchain-tree SHA-256 `95d4801160fbd483c64db9537da4b359d568e63a2c053de6cf2d1a9fb475c640`. `Cargo.lock` had SHA-256 `981d86851f56371ac454c62ec404a3e1f53890782e33d526252a856700f68248`.

The signed upstream Zsh 5.9.2 archive had SHA-256 `36fa734374b44783582cec09bcd67822e2f992c779ec1624ab5596df078d2f81`, with signer fingerprint `7CA7ECAAF06216B90F894146ACF8146CAE8CBBC4`. The effective C compiler was GCC 8.5.0, and the linker was GNU ld 2.30. Both workers used `SOURCE_DATE_EPOCH=1788328059`, `LANG=C`, `LC_ALL=C`, `TZ=UTC`, umask `022`, and one build job for Rust and Zsh.

## Reproduction

From a clean checkout with the locked Rust toolchain available:

```sh
./build/test-reproducible-development-bundles.zsh build/portable/reproducibility-947d812 947d8122254494d4c3f5d8ea9855a56d21d90e1a
```

[`result.txt`](result.txt) is the machine-readable comparison record. [`manifest.json`](manifest.json) is the common exact bundle manifest. [`worker-a.log`](worker-a.log) and [`worker-b.log`](worker-b.log) retain the complete build and test output. The two 2.4 MB archives are ignored build products and can be regenerated with the command above.

## Failed source-identity attempt

The first harness attempt at revision `6f3ad33289343567b16b06750c77e290f6b046d2` completed compilation but stopped before producing a manifest because the container could not follow the detached worktree's `.git` pointer into the main repository. The observed error was `fatal: not a git repository: /code/wsh/.git/worktrees/worker-a`. Revision `947d8122254494d4c3f5d8ea9855a56d21d90e1a` resolves the exact source revision on the host and passes it into the container, and it pins both Rust and Zsh to one build job. The raw failed log is retained in [`failed-source-identity-worker.log`](failed-source-identity-worker.log).

This result proves repeatability across two isolated builds on one host using the same local Rust toolchain tree and container infrastructure. It does not establish independent build organizations, GitHub provenance, release immutability, or official release status.
