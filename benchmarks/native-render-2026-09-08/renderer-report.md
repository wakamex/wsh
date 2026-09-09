# C rendering preserves prompt bytes within the fixed cost gate

The C renderer matches Rust in 45,600 comparisons under ASan/UBSan and again in an optimized build. The largest paired p95 render-cost increase is 2.950 microseconds, below the predeclared 50-microsecond limit. This completes the renderer prototype; integrating the collector, renderer, protocol and tracing into a complete C helper remains separate work.

| Theme | Rust median render, microseconds | C median render, microseconds | Paired p95 increase, microseconds |
|---|---:|---:|---:|
| Minimal | 1.870 | 3.925 | 2.650 |
| Wakamex | 1.476 | 3.290 | 2.950 |
| Robbyrussell | 1.630 | 3.451 | 2.290 |
| Agnoster | 2.120 | 4.205 | 2.651 |

## Correctness and dependency evidence

The comparison calls the actual Rust renderer and the C renderer with the same stateful sequence. Four shipped themes run in four environments; 22 additional definitions cover truncation limits and every foreground/background color with partial segment styling. Each combination runs 1,200 cases, covering raw non-UTF-8 paths and environment values, long Unicode paths, repeated snapshots, transient reset, home matching, hostile prompt text, Git labels and operation states, duration boundaries through u64 maximum, privilege and exit status. Both sanitized and optimized runs preserve exact left/right prompt bytes. The initial 19,200-case pass is retained alongside expanded coverage.

The pinned yyjson source passes all 12 upstream test groups under ASan/UBSan with leak detection and no exclusions. It currently serves only the comparison driver's JSON exchange. Its full-width integer API will be evaluated against the real runtime protocol in the next slice. The Wsh renderer still uses the previously tested TOML definitions and validator. No theme migration is introduced.

## Timing method

A release Rust test process and optimized C driver run sequentially on CPU 0. For each shipped theme, one warmup pair precedes 1,000 retained pairs, alternating which implementation runs first. Both clocks enclose only rendering; JSON exchange, process startup, theme parsing and caller destruction remain outside. The same deterministic fixture sequence includes long values and transient state. Separate empty-clock observations have 20 ns medians in both implementations and a 10 ns paired p95 difference. No instrumentation overhead is subtracted. Sanitizer timings are diagnostic and do not enter this gate.

The C implementation is slower in this isolated workload but passes the fixed regression threshold. There is no speedup claim. Total helper memory, startup, repaint, trace overhead, installed size and maintenance cost require the complete helper comparison. The test-only driver is not a shipped runtime interface. Production continues to use Rust rendering.

## Reproduction and retained inputs

Run `native/build-render-driver.zsh OUTPUT` for the optimized driver or prefix it with `CC=clang CFLAGS='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer'` for sanitizer coverage. Set `WSH_RENDER_DRIVER` to its `render-driver` and `WSH_RENDER_OUTPUT` to a fresh JSON path, then run `cargo test --offline --locked -p wsh-runtime native_renderer_matches_rust -- --ignored --nocapture`. Use `--release` for the optimized comparison. Add `WSH_RENDER_BENCHMARK=1` and prefix the release command with `taskset -c 0` for timing.

`renderer-metadata.json` identifies exact source and executable hashes, toolchains and commands. `renderer-inputs.tar.gz` preserves source, fixtures and definitions; `renderer-results.tar.gz` retains raw comparisons, logs and computed timings. The shared evidence entrypoint verifies counts, parity and the fixed threshold. These standalone development artifacts contain no Zsh binary or installation payload; shell-level qualification is pending the complete helper.
