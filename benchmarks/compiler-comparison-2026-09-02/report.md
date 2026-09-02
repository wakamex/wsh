# GCC 16.2 and Clang 23.1 did not improve the bundled Zsh workload

Neither current stable compiler produced a consistent performance improvement over Rocky GCC 8.5 with the rest of the release recipe fixed. GCC 16.2 was 0.014 ms slower in the first interactive block and 0.012 ms faster in the reverse-order block. Clang 23.1 matched GCC 8.5 in the reverse block but was 0.029 ms slower in the first block. Repeated non-interactive startup medians differed by 11 us across all three compilers, and each compiler's observed range overlapped the others. GCC 8.5 remains the default.

The comparison rebuilt signed Zsh 5.9.2 with each compiler against the same Rocky Linux 8.10 headers, glibc 2.28 libraries, GNU ld 2.30, configure arguments and default `-O2` optimization. Every bundle passed the upstream Zsh suite, 21 Rust tests, relocation, manifest, provider, PTY, cleanup, dynamic-library and glibc-floor checks. The accepted PTY matrix then collected 2,520 timed prompt samples in forward and reverse compiler order, with pre-run and post-run timer calibration and per-target CPU-pressure admission.

## Raw Zsh and repeated startup stayed within run-order spread

The interactive values pool the same clean, tracked-dirty and untracked state mix from the minimal and Wakamex runs. Each block contains 120 raw samples per compiler, and the pooled column contains 240. The startup value is the median mean duration from ten observations of 5,000 `zsh -f -c exit` launches pinned to CPU 0.

| Zsh compiler | Block A raw median | Block B raw median | Pooled raw median | Pooled raw p90 | Pooled raw maximum | Startup median | Zsh executable |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GCC 8.5 | 0.383 ms | 0.411 ms | 0.391 ms | 0.462 ms | 0.521 ms | 1,874 us | 837,768 bytes |
| GCC 16.2 | 0.397 ms | 0.399 ms | 0.398 ms | 0.464 ms | 0.600 ms | 1,883 us | 870,416 bytes |
| Clang 23.1 | 0.412 ms | 0.411 ms | 0.411 ms | 0.472 ms | 0.557 ms | 1,872 us | 887,776 bytes |

The GCC 16.2 comparison changed sign when compiler order was reversed. Clang also lost its apparent raw disadvantage in the reverse block. The 2 us startup difference between Clang and GCC 8.5 is 0.1 percent, while their observed aggregate ranges were 1,856-1,894 us and 1,856-1,896 us. These results do not support selecting a compiler for speed.

## Complete prompt latency did not establish a compiler effect

The complete-runtime values pool 120 samples per renderer and compiler. Each added value subtracts the matching pooled raw statistic. The runtime executable, integration, theme definition, fixture and non-Zsh bundle payload were byte-identical across compiler variants.

| Compiler | Minimal first median added | Minimal settled median added | Minimal settled p90 added | Minimal settled maximum added | Wakamex first median added | Wakamex settled median added | Wakamex settled p90 added | Wakamex settled maximum added |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GCC 8.5 | 0.624 ms | 6.746 ms | 11.563 ms | 20.402 ms | 0.547 ms | 6.429 ms | 6.751 ms | 8.165 ms |
| GCC 16.2 | 0.632 ms | 6.764 ms | 7.137 ms | 10.291 ms | 0.505 ms | 6.245 ms | 6.545 ms | 7.222 ms |
| Clang 23.1 | 0.610 ms | 6.688 ms | 7.033 ms | 7.656 ms | 0.559 ms | 6.373 ms | 6.757 ms | 7.604 ms |

The GCC 8.5 minimal pool includes isolated settled outliers in different states in the two order blocks. GCC 16.2 also recorded a 10.311 ms worst state-and-block maximum, and Clang's 7.349 ms worst state-and-block p90 exceeded the fixed 7.1 ms gate. The non-Zsh runtime and Git work were identical, and the tail changes did not repeat by state or order. They are retained as variability evidence rather than attributed to the C compiler.

All timed semantic checks passed, every wsh transition used one Git process with optional locks suppressed, and each changed result produced one repaint. All 12 wrapper runs passed calibration and CPU-pressure admission. Wrapper acceptance means the evidence is structurally valid; it does not mean every pooled or state-level product latency threshold passed.

## Fixed build inputs

The bundle source revision was `299882284db0019ec8d1a95d077fad01519cef30`. The benchmark revision was `8dc0b5fea25671d6745a556bffb740d3866e189c`. Zsh came from the signed 5.9.2 archive with SHA-256 `36fa734374b44783582cec09bcd67822e2f992c779ec1624ab5596df078d2f81`. Every compiler used the same configure arguments `--enable-cap --enable-multibyte --enable-pcre`, configure-selected `-O2`, one build job, `LANG=C`, `LC_ALL=C`, `TZ=UTC`, `umask 022`, the source commit timestamp and the locked Rocky Linux 8.10 package set.

| Variant | Compiler input | Installed compiler tree | Bundle manifest | Zsh SHA-256 | Archive bytes |
| --- | --- | --- | --- | --- | ---: |
| GCC 8.5 | Locked Rocky RPM `gcc-8.5.0-28.el8_10.x86_64` | Part of the complete RPM lock | `7943131a8972ccbad02ba9ba46d38c3396b982ccb39aead7b6557aad2226155a` | `09f0cd11e7a69684ee732b4fe74b280aaf3ec42fdec6c311335df002d2311274` | 2,387,620 |
| GCC 16.2 | [Signed GCC 16.2.0 source](https://gcc.gnu.org/pub/gcc/releases/gcc-16.2.0/) SHA-256 `e6738e29597f733270731aa90600f37ffdc045079dfc27ec7e8192cc81085c3e` | `3c16c77653877eeadee0c40c604a86a696b93d500e48ca9551da8828d5e56ccc` | `4d96286347355efc3bca71bfb93c864c91bc4f5e497846c357e5e2a29e256333` | `7d9d7cd73733394bfb771773573adbbaa3e3b575b8042bf256505f7d29795659` | 2,445,744 |
| Clang 23.1 | [LLVM 23.1.0 Linux X64 release](https://github.com/llvm/llvm-project/releases/tag/llvmorg-23.1.0) SHA-256 `18da30f77f475688a18f7704d23f9f155ae007ed9922dbed6850a9419d9fec8c` | `898958d0ffb9709d2d54c3bb5bc21dd5bbe8303d101f52432c383f484c70d2a1` | `5721473e18a460cb66e6757c183f657bc10cca51e8685a8558ce951c45d78de0` | `97187278b55d42fae3c301e7193278d03053a1f851d36d8794fe6224529d5fb7` | 2,403,680 |

GCC 16.2 was built in a separate bootstrap container with C as its only enabled language, then only its installed compiler tree entered the locked target builder. The official Clang executable itself requires a newer host glibc and libstdc++ than Rocky 8. It ran from a private `/clang` loader and runtime tree whose digest is included above; it still compiled against Rocky headers and libraries and invoked the target builder's GNU ld 2.30. The resulting bundle imported no symbol newer than `GLIBC_2.28`. This runner adaptation affects how the compiler executes, not the target ABI, but it would need its own pinned construction recipe before Clang could become a release toolchain.

The three manifests contain the same runtime SHA-256 `57bc72c1c92472ccfb05e677071bf95d82fff4df3044f34a92a629596b62cd1b`. Excluding `bin/zsh` and `lib/zsh`, their file records are identical. GCC 16.2 and Clang increased the Zsh executable by 32,648 and 50,008 bytes respectively, and neither produced a smaller complete archive than GCC 8.5.

## Retained evidence

[`pooled-summary.tsv`](pooled-summary.tsv) contains the pooled values and worst state-and-block gates. [`startup.tsv`](startup.tsv) retains every startup observation, and [`startup-metadata.txt`](startup-metadata.txt) records its binary identities and the serialization-only delimiter repair. Each block and compiler directory retains the wrapper's summary, all timed samples, telemetry, calibration metadata and generated distribution. The commands and adoption rule were fixed before measurement in [`../compiler-comparison-plan-2026-09-02.md`](../compiler-comparison-plan-2026-09-02.md).

Reconsidering the compiler requires a new measured hypothesis, such as a new Zsh release, a named compiler correctness fix, or a separately gated optimization configuration such as LTO or profile-guided optimization. Compiler recency alone is not enough to repeat or broaden this comparison.
