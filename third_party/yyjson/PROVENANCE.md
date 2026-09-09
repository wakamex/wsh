# yyjson prototype provenance

The C source, header and MIT license are byte-identical to [ibireme/yyjson](https://github.com/ibireme/yyjson) revision `6447536015f3d600f3d65323b10976103b337ca7` (source version 0.13.0). `SHA256SUMS` binds the vendored bytes. There are no Wsh source patches.

The opt-in C runtime prototype evaluates this parser to preserve the existing full-u64 request and generation contract. It uses strict JSON and UTF-8 behavior; application code remains responsible for allowed fields, duplicates, types, integer ranges and protocol bounds. All 12 upstream test groups pass ASan/UBSan with leak detection and no exclusions. Wsh runtime protocol comparison remains required before runtime adoption under [the native runtime plan](../../benchmarks/native-render-2026-09-08/plan.md). This dependency is not part of the default Rust runtime.
