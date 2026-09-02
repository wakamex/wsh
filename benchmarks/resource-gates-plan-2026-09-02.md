# Trace overhead and retained memory receive fixed phase-one gates

The phase-one release gates already bound normal prompt latency, process count, optional-lock behavior, repainting, and semantics, but tracing overhead and retained memory were recorded without pass thresholds. This experiment fixes both gates before the accepted run. Tracing may add at most 0.5 ms to first-editable p90 and 0.5 ms to settled p90. The combined Zsh and runtime path may add at most 4,096 KiB of retained PSS at p90 and 5,120 KiB at maximum over raw bundled Zsh.

The trace thresholds come from the feature's purpose and two earlier accepted measurements. Tracing must remain useful during performance diagnosis without consuming a material fraction of the 7.1 ms settled-latency budget. In the current fixed run, the largest trace-minus-untraced p90 differences were 0.127 ms first-editable and 0.345 ms settled. In the preceding accepted reproduction they were 0.257 ms and 0.399 ms. A 0.5 ms ceiling covers those observations while limiting tracing to 7 percent of the normal settled budget.

The retained-memory gate applies per interactive session because phase one starts one runtime for each Zsh process. A three-pair instrumentation pilot after five prompts measured 1,993-2,003 KiB of added PSS. The 4 MiB p90 gate allows roughly twice that pilot value, and the 5 MiB maximum catches isolated excessive retention without making page-accounting noise a release failure. Twenty panes at the p90 ceiling would add 80 MiB. This gate covers retained idle memory, not transient Git child memory while a request is running.

## Accepted trace workload

The accepted trace comparison uses the pinned 1,000-file Git fixture and 20 clean, tracked-dirty, and untracked transitions per target. It runs two separately calibrated blocks with target order reversed: `wsh,wsh-trace` and `wsh-trace,wsh`. Each state and block computes `wsh-trace p90 - wsh p90`; the gate uses the largest signed difference. Both targets must retain full semantic, process, optional-lock, and repaint behavior. The trace file remains bounded and private under the existing correctness test.

## Accepted memory workload

The accepted retained-memory comparison uses 20 paired fresh sessions of raw bundled Zsh and bundled Zsh plus the runtime. Pair order alternates. Both run in the same committed 1,000-file repository fixture. Each process reaches an editable prompt, runs 20 prompt cycles, waits 250 ms without input, and then reads `Pss` from Linux `/proc/PID/smaps_rollup`. The wsh observation is the sum of the Zsh and runtime PSS; added PSS subtracts the paired raw-Zsh PSS. The p90 is nearest-rank over the 20 added values, matching the latency benchmark's percentile rule.

The accepted run must use a clean glibc 2.28 development bundle built after these thresholds are committed. It records the source revision, bundle manifest, all measured file digests, benchmark revision and runner digest, host, commands, raw measurements, generated summaries, and admission results. A failure does not change these thresholds. It starts a measured attribution experiment with one causal intervention and a two-attempt limit.
