# Active launch no longer hashes the complete bundle

Normal `wsh` launch added 38.1 ms at the median because it inspected and hashed all 1,282 files in the selected 12 MB bundle twice before starting Zsh. Reusing the activation-time verification record and checking only the recorded manifest identity and four required entrypoints reduced the median added cost to 1.6 ms, under the fixed 2.0 ms gate. The direct bundled-Zsh control remained at 1.8 ms.

The comparison measured 1,000 launches per variant as ten observations of 100 sequential `-f -c exit` launches pinned to CPU 0. Forward and reverse blocks changed variant order, both variants received 20 warmup launches, and the before and after measurements used the same content-addressed bundle and command. Each added value subtracts the direct observation with the same block and repetition.

| Path | Direct median | Managed median | Paired added median | Paired added range | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| Baseline | 1.8 ms | 39.95 ms | 38.1 ms | 37.5-78.4 ms | Fail |
| Activation-backed launch | 1.8 ms | 3.4 ms | 1.6 ms | 1.5-1.7 ms | Pass |
| Activation-backed launch, glibc 2.28 floor build | 1.85 ms | 3.5 ms | 1.65 ms | 1.5-1.8 ms | Pass |

Full payload verification remains mandatory when a bundle is built, explicitly verified, activated, or selected for rollback. Normal launch reads the bounded state and manifest, requires the manifest digest recorded by activation, validates the manifest schema, and checks the type, size, and mode of the shell, runtime, integration, and theme entrypoints. It does not claim to detect post-activation mutation of every installed file. `wsh bundle verify` remains the complete integrity check, and its test detects a same-size payload mutation that the activation-backed launch intentionally does not rehash.

The earlier prompt and retained-memory results launched the bundled Zsh and runtime directly. Their numerical results are unchanged because neither path invoked the manager. This experiment adds the missing manager-dispatch measurement; it does not retroactively include manager residency in the earlier memory scope or manager dispatch in the earlier first-editable scope.

[`baseline.tsv`](baseline.tsv), [`fast-launch.tsv`](fast-launch.tsv), and [`floor-fast-launch.tsv`](floor-fast-launch.tsv) retain every timing observation. [`metadata.txt`](metadata.txt) records the source, manager, bundle, Zsh, toolchain, host, CPU, workload, and command identities. The floor build passed all Rust and upstream Zsh tests, relocation, a real provider request, PTY behavior, cleanup, dependency recording, and the `GLIBC_2.28` symbol ceiling. The gate and one-attempt limit were fixed before the intervention in [`../manager-launch-plan-2026-09-02.md`](../manager-launch-plan-2026-09-02.md).
