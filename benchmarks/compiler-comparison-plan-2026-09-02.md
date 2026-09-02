# GCC 16.2 and Clang 23.1 compiler comparison

The experiment asks whether a current stable C compiler materially improves the bundled Zsh path while preserving the glibc 2.28 runtime floor. It compares the existing Rocky GCC 8.5 build, upstream GCC 16.2.0, and upstream Clang 23.1.0. No compiler becomes the default from version recency alone.

## Fixed inputs

- wsh source revision and Rust binary
- Signed upstream Zsh 5.9.2 source with SHA-256 `36fa734374b44783582cec09bcd67822e2f992c779ec1624ab5596df078d2f81`
- Empty Zsh patch set
- Configure arguments `--enable-cap --enable-multibyte --enable-pcre`
- Configure-selected default optimization flags
- Rocky Linux 8.10 final build environment, complete RPM lock, glibc 2.28 headers and libraries, GNU assembler and GNU ld 2.30
- `x86_64-unknown-linux-gnu` with the compiler's generic x86-64 default rather than host-specific instruction selection
- Locale `C`, timezone `UTC`, umask `022`, one Zsh build job, and the source commit timestamp
- The same runtime, integration, theme definitions, 1,000-file fixture, 150 ms settle interval, and benchmark instrumentation

Compiler construction happens in a separate container stage. Only the installed compiler tree enters the final Rocky builder, so compiler-build dependencies cannot change Zsh feature detection. GCC and Clang both invoke the final builder's GNU ld 2.30. Clang's integrated assembler remains part of the Clang implementation being compared.

## Compiler identities

| Variant | Pinned input | Authentication |
| --- | --- | --- |
| Baseline | Rocky GCC 8.5.0-28 | Complete locked RPM identity and payload digest |
| GCC | [GCC 16.2.0 source](https://gcc.gnu.org/pub/gcc/releases/gcc-16.2.0/) | Upstream SHA-512 `c51c30ca7422d0cbecf504b2e0f33c3aca31e0f90a76b65217f465163fa6fa17b3f5de39e145c47e5bab90ac0ce7fff3b03c8d553ae36e01faaea5a50f8648d1` plus the release signature |
| Clang | [LLVM 23.1.0 Linux X64 release asset](https://github.com/llvm/llvm-project/releases/tag/llvmorg-23.1.0) | Release-workflow Sigstore provenance with subject SHA-256 `18da30f77f475688a18f7704d23f9f155ae007ed9922dbed6850a9419d9fec8c` |

## Correctness and compatibility gates

Each variant must pass the upstream Zsh suite, 21 Rust tests, manifest and relocated-bundle verification, a real provider request, interactive PTY repaint, crash, and cleanup tests, exact dynamic-library recording, and the maximum imported `GLIBC_2.28` symbol check. The installed payloads must differ only in Zsh files and compiler metadata; the runtime, integration, schemas, themes, Zsh source, configure arguments, and recorded system-library boundary must match.

## Performance method

Each passing compiler runs through the accepted `zsh-theme-bench` wrapper with 20 clean, tracked-dirty, and untracked iterations, plus staged and detached-HEAD semantic checks. One run covers raw Zsh, idle wsh, direct Git, the minimal renderer, and traced minimal rendering. A second run covers matched raw Zsh and the Wakamex renderer. Compiler order is reversed in a second block to expose time-order effects. Every run must pass pre-run and post-run timing calibration and CPU-pressure admission.

The primary comparison reports raw first-prompt median, p90, and maximum plus the complete renderers' first-editable and settled median, p90, and maximum deltas over their matched raw controls. Process, optional-lock, repaint, and semantic gates remain unchanged. A compiler is preferred only when it passes every gate and its improvement is consistent across the reversed-order blocks rather than arising from one favorable run. A result inside run-to-run spread is reported as inconclusive, and fixed latency gates are not changed to admit a compiler.

The experiment also records executable sizes and a repeated non-interactive Zsh startup workload. These diagnostic measurements can explain a result but cannot override the interactive product workload.
