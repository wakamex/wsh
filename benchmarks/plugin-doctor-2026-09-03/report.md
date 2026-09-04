# Plugin doctor identifies exact redundant declarations without changing configuration or startup

`wsh doctor` correctly recommended removing exact redundant declarations of history substring search, autosuggestions, and syntax highlighting. It preserved and reported all three modified implementations, made no recommendation when the Wsh defaults were disabled, and left every tested `.zshrc` byte-identical. The existing plugin and general configuration coexistence suites continued to pass.

The command starts one separate diagnostic shell through the normal managed startup path and reads the ownership decisions already produced by the three adapters. It does not parse Zsh source or guess which line loaded a plugin. A private report is limited to 4,096 bytes, malformed or inconsistent fields fail closed, and the diagnostic child has a 10-second deadline. Older bundles without ownership fields produce an explicit unsupported result.

Ordinary `wsh` startup executes no doctor path. Against the same edge-Zsh bundle and isolated empty user configuration, managed first-editable p90 changed from 30.409 ms to 29.940 ms across 40 retained launches per build. The -0.468 ms difference passes the fixed maximum regression of +0.5 ms.

## Correctness cases

The fixture loaded the actual files in the bundle rather than substitute implementations. Each case hashed `.zshrc` before and after diagnosis.

| User configuration | Diagnosis | Runtime treatment |
|---|---|---|
| No external copy | No finding | Wsh defaults remain active |
| Exact pinned history search | Remove redundant declaration | Wsh takes ownership |
| Exact Oh My Zsh history search copy | Remove redundant declaration | Wsh takes ownership |
| Exact pending autosuggestions | Remove redundant declaration | Wsh takes ownership |
| Exact already-active autosuggestions | Remove redundant declaration | Exact external copy remains the current owner |
| Exact syntax highlighting | Remove redundant declaration | Exact external copy remains active or receives its missing upstream hooks |
| Modified copy of each plugin | Preserve, with no removal suggestion | Modified external implementation remains authoritative |
| Exact external copies with each Wsh default disabled | No finding | External implementation remains authoritative |

The command names the redundant component and tells the user to remove its startup declaration. It does not claim a source location because the adapter's ownership result proves the loaded bytes, not the declaration syntax that selected them.

## Startup comparison

Both managers were built with Rust 1.95.0 in the release profile and launched the same bundle on CPU 0. Each variant ran 5 warmups followed by 20 forward-order and 20 reverse-order retained launches. Timing began before PTY creation and ended at the first editable prompt.

| Build | Variant | Median, ms | p90, ms | Maximum, ms |
|---|---|---:|---:|---:|
| Baseline | Raw Zsh | 4.711 | 4.834 | 5.875 |
| Baseline | Direct complete bundle | 28.692 | 29.280 | 31.002 |
| Baseline | Managed complete bundle | 29.062 | 30.409 | 31.629 |
| Candidate | Raw Zsh | 4.698 | 4.910 | 5.470 |
| Candidate | Direct complete bundle | 28.641 | 29.172 | 29.455 |
| Candidate | Managed complete bundle | 28.287 | 29.940 | 31.470 |

The first pilot inherited the host's live Zsh configuration in the managed variant but not the direct control. It produced roughly 1.3-second managed values that primarily measured unrelated configuration and was rejected before interpreting the candidate difference. Those raw samples are retained as `discarded-host-config-baseline.tsv` and `discarded-host-config-candidate.tsv`. The accepted rerun set the same isolated empty user `.zshrc` for both managers.

The complete canonical build then repeated the Rust suite, relocated bundle checks, runtime PTY suite, general configuration coexistence, all three editing-default suites, the new doctor fixture, and the maximum imported-symbol check at the glibc 2.28 floor. Development bundle `262cc493b6a5cad87ac63f69a0761d9c381ad11d403b8875e34a3b0e89124066` passed with `GLIBC_2.28` as its newest imported symbol.

## Reproduction

```sh
./tests/plugin-doctor.zsh target/release/wsh <bundle>
./tests/history-substring-search.zsh target/release/wsh <bundle>
./tests/autosuggestions.zsh target/release/wsh <bundle>
./tests/syntax-highlighting.zsh target/release/wsh <bundle>
./tests/zsh-config-coexistence.zsh target/release/wsh <bundle> present

env -u ZDOTDIR HOME=<empty-home> WSH_FIRST_EDITABLE_CPU=0 ./benchmarks/benchmark-first-editable.zsh <baseline.tsv> <baseline-manager> <bundle>
env -u ZDOTDIR HOME=<empty-home> WSH_FIRST_EDITABLE_CPU=0 ./benchmarks/benchmark-first-editable.zsh <candidate.tsv> <candidate-manager> <bundle>
./benchmarks/summarize-plugin-doctor.zsh <baseline.tsv> <candidate.tsv> <summary.tsv>
```

The exact source, bundle, binaries, host, commands, raw-input hashes, and sample rules are recorded in [`metadata.txt`](metadata.txt).
