# Zeroed Zsh dump padding restores reproducible bundles

Two isolated builds of Wsh revision `45c220a1c50a664db191549eba321b1f465a4858` produced byte-identical bundle manifests, canonical archives, launchers, installers, and bootstrap scripts after a five-line Zsh write-path correction. The shared archive SHA-256 was `13d4f8fe57b73ea1c4d4950c979077299dc78c659a65942dfab43b8e1cf73430`, and the shared manifest and bundle identity was `543c0ee14bcedb45c86fa79152028f5d8e016ad4cc221cfb2b0d5130d2045a7b`.

The original clean two-build gate stopped because one compiled syntax-highlighter file differed. Zsh wrote two uninitialized alignment bytes into each byte-order copy of that `.zwc` file. The patch writes the initialized program bytes followed by explicit zero padding, preserving the existing format while removing the varying bytes and potential stale heap contents.

| Output | Worker A | Worker B |
| --- | --- | --- |
| Canonical archive SHA-256 | `13d4f8fe57b73ea1c4d4950c979077299dc78c659a65942dfab43b8e1cf73430` | `13d4f8fe57b73ea1c4d4950c979077299dc78c659a65942dfab43b8e1cf73430` |
| Manifest SHA-256 | `543c0ee14bcedb45c86fa79152028f5d8e016ad4cc221cfb2b0d5130d2045a7b` | `543c0ee14bcedb45c86fa79152028f5d8e016ad4cc221cfb2b0d5130d2045a7b` |
| Launcher SHA-256 | `f7f9417807d7a4679a36b66b8926e96e2f4cc9651659c6279823d148884f4fb9` | `f7f9417807d7a4679a36b66b8926e96e2f4cc9651659c6279823d148884f4fb9` |
| Installer SHA-256 | `07009732bb8f8685ca0f5e12643f334d5bc4fed906030cf117cb844e0fc56be2` | `07009732bb8f8685ca0f5e12643f334d5bc4fed906030cf117cb844e0fc56be2` |
| Bootstrap SHA-256 | `b79f5b3bc13bb5ab5da3dec054b6715b41daeb4a1987d457255d30bd59fc3eb9` | `b79f5b3bc13bb5ab5da3dec054b6715b41daeb4a1987d457255d30bd59fc3eb9` |
| Archive size | 2,487,964 bytes | 2,487,964 bytes |
| Complete glibc 2.28 suite | Pass | Pass |

## Reproduced failure and native correction

Revision `7fefaa6b7083c3fd174536b240a2dc94005a79d3` built the same Zsh source and byte-identical Zsh executables in two clean worktrees. Its manifests differed only at `share/wsh/defaults/zsh-syntax-highlighting/highlighters/line/line-highlighter.zsh.zwc`. Worker A recorded SHA-256 `d5f2768e763c90dd34e12ed168b1b07f608f2dccf95f9c2d0fe8bc0923a0dc98`; worker B recorded `e7404267c958facec01acc67b49d54416132994db176d1de3a17b74e6159fa2f`. `cmp -l` found different bytes at positions 459-460 and 919-920, the last two alignment bytes in each byte-order copy.

Source inspection found that `write_dump()` calculated a rounded `wordcode` count and passed the rounded byte length to `write_loop()`, although the program allocation's logical length ended before the alignment padding. Patch `build/zsh-patches/cad0d67c-zcompile-padding.patch`, SHA-256 `d1da8d32b8afa27bb0516c81f63345ea1196edf177bdae151fe9f2ad617776a6`, writes the logical initialized length and then zeroes the required padding. It changes no parser, evaluator, or dump-reader behavior.

The focused regression compiles the same vendored source in two isolated directories, compares the complete files, and checks the final alignment bytes in both byte-order copies. The unpatched Wsh Zsh fails on nonzero padding; the patched build passes. All 75 upstream Zsh test scripts also passed with 0 failures and the same 2 existing skips, as recorded in [`zsh-upstream.log`](zsh-upstream.log).

## Complete isolated build

Each worker used its own detached worktree, Cargo home, Cargo target directory, Zsh output directory, bundle directory, and container build context. Both ran the upstream Zsh suite, Rust workspace tests, the runtime PTY suite, user-configuration coexistence, the three interactive defaults, plugin doctor, foreground startup, native terminal integration, the new compiled-function check, relocation, manifest verification, and glibc symbol inspection. Every included ELF stayed at or below `GLIBC_2.28`.

[`result.txt`](result.txt) records the compared hashes. [`manifest.json`](manifest.json) is the shared exact bundle manifest. [`worker-a.log`](worker-a.log) and [`worker-b.log`](worker-b.log) retain the passing builds. The two canonical archives are ignored build products and can be regenerated.

The failed manifests and logs are retained as [`failed-worker-a.manifest.json`](failed-worker-a.manifest.json), [`failed-worker-b.manifest.json`](failed-worker-b.manifest.json), [`failed-worker-a.log`](failed-worker-a.log), and [`failed-worker-b.log`](failed-worker-b.log). The [experiment plan](../zcompile-reproducibility-plan-2026-09-04.md) fixes the counterfactual and thresholds.

## Reproduction

From a clean checkout with the locked Rust toolchain available:

```sh
./build/test-reproducible-development-bundles.zsh build/portable/reproducibility-45c220a 45c220a1c50a664db191549eba321b1f465a4858
```

The two-build result establishes repeatability on one host with the same pinned toolchain and container infrastructure. Independent release builders and their attestations remain the release-level provenance check.
