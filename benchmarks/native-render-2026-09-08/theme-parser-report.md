# C theme validation preserves the tested definitions

The C theme validator matches Rust on 1,596 comparisons, including all four shipped themes, numeric boundaries and 1,000 deterministic byte mutations. Both sanitizer and release builds pass. Parsing adds about 17–20 microseconds at the median, within the fixed +0.5 ms paired p95 gate. This is a tested standalone prototype; rendering and the complete C runtime are still pending.

| Theme | Rust median parse/validate/free, microseconds | C median parse/validate/free, microseconds | Paired p95 C regression, microseconds |
|---|---:|---:|---:|
| Minimal | 20.181 | 36.861 | +20.680 |
| Wakamex | 20.311 | 37.096 | +19.311 |
| Robbyrussell | 20.240 | 37.051 | +19.291 |
| Agnoster | 22.696 | 42.941 | +23.561 |

## Correctness and dependency changes

The comparisons invoke the actual Rust validator and C executable on the same bytes. They cover missing and duplicate fields, field types, unknown tables, quoted keys, Unicode character limits and controls, component duplication, segment consistency, file-size limits, shell-looking literals, and the full unsigned-64-bit duration threshold range. Six additional file cases verify ordinary files, missing paths, directories, symlinks, FIFOs and unreadable files. The C reader uses one nonblocking, no-follow descriptor with a bounded read. Definitions remain non-executable TOML schema version 1.

The pinned tomlc17 dependency initially passed its standard corpus while rejecting a valid long binary integer. Strict UBSan also stopped at its allocator's null-pointer offset expression. Private build copies receive three separately tested changes: use `offsetof`, read complete numeric tokens, and provide an opt-in u64 representation matching the existing Rust decoder. Original vendored source remains byte-identical to upstream. [Provenance](../../third_party/tomlc17/PROVENANCE.md) records the source and these maintenance costs.

The patched parser passes 220 valid and 493 invalid conformance cases under ASan/UBSan, with the upstream TOML-1.1 exclusion for `invalid/key/special-character`. A separate pass over 779 corpus files checks sanitizer diagnostics and process status, including rejected inputs, so a sanitizer crash cannot count as a successful syntax rejection. All ten local upstream test targets pass after the final patch. Twenty integer boundary cases compare the extended integer behavior with the real Rust theme decoder. Wsh's sanitizer builds use leak detection and no sanitizer exclusions.

The standalone Wsh validator comprises 168 implementation lines, a 15-line header and a 14-line CLI. Its release executable is 63,208 bytes. These are partial costs: the parser dependency, its patch, build rule and remaining renderer/runtime must be counted before choosing a complete implementation. This result does not claim that the standalone validator replaces the currently shipped helper.

## Measurement and reproduction

The source baseline is `53f020a` plus the archived inputs. The microbenchmark measures parsing, validation and destruction of an already-read source string. For each theme it retains 1,000 alternating Rust/C pairs after one warmup per variant, with both processes pinned to CPU 0. Pipe exchanges and process startup stay outside the timed spans. The same count of empty-clock pairs has a 20 ns median for each implementation and a 10 ns paired p95 difference. No instrumentation cost is subtracted from the reported values.

`theme-parser-metadata.json` records exact binaries, source hashes, toolchains and commands. `theme-parser-inputs.tar.gz` preserves implementation, dependency, patch and harness bytes. `theme-parser-results.tar.gz` preserves failed and passing checks, raw timing rows and summaries. The shared retained-evidence suite verifies the comparison counts, identities and fixed arithmetic through `verify-native-theme-parser-evidence.py`.
