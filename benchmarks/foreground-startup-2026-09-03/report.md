# Structured foreground startup preserves stopped jobs without material startup cost

`wsh run-foreground` preserved the exact application argument vector and the owning Zsh job table, including Ctrl-Z followed by `fg`, while reaching application readiness 1.534 ms sooner at p90 than Wakterm's positional wrapper in the accepted run. It returned to an editable prompt 513.358 ms sooner at p90 in the tested fixture because it retained one initialized Zsh instead of replacing the wrapper with a second interactive shell.

The experiment compared Wakterm's reconstructed-command wrapper, the cheapest positional-argument counterfactual, and one Wsh-owned interactive Zsh under the same PTY, bundled Zsh, isolated configuration, Git fixture, CPU affinity, and C probe. The candidate also passed the ordinary managed-startup regression gate and executed one Zsh instead of two.

## The positional wrapper still loses a stopped job

Wakterm's current wrapper serializes the application argument vector into quoted shell source, runs it through an interactive login shell, then replaces that shell with another login shell. Passing the command through `"$@"` avoids source reconstruction and supports Unix non-UTF-8 arguments, but does not preserve job ownership when the application stops. Both wrappers reproduced the same failure after Ctrl-Z:

```text
fg: no current job
```

The accepted path passes the original argument vector to the bundled Zsh through `-i -s`. Bundle `.zshenv` captures the parameters before user startup files, and a one-shot first `precmd` callback runs the array directly. The same Zsh owns the foreground job, stopped-job table, and normal prompt.

## Correctness passed across arguments, signals, jobs, and startup files

The probe and PTY test passed every fixed gate:

- Empty, whitespace, quoted, multiline, wildcard, dollar-sign, leading-dash, Unicode, and Unix `0xff` arguments arrived byte for byte.
- The application process group owned the controlling terminal, and a nested child remained in the same process group.
- Default Ctrl-C terminated the application and returned one prompt without a zombie.
- An application that consumed Ctrl-C remained foreground and produced no premature prompt.
- Ctrl-Z stopped the application, `fg` resumed the same PID and process group, and the next Ctrl-C returned one prompt.
- Exit 0, exit 7, interrupt, and a deliberate terminal-mode mutation left a usable terminal and prompt.
- Login and non-login user startup files ran once with their native scope. An existing alias and `precmd` hook remained available.
- Ordinary `wsh run` ignored an inherited foreground-launch marker instead of activating the one-shot path.
- Twenty fresh repeated launches accumulated no startup-file loads, process layers, stopped jobs, or terminal-state damage.

Wakterm's authoritative `restored_harness_runs_as_a_shell_child` unit also passed at revision `b5c285fc5cd542862987b8eb7bf5b229115d9991`. That unit covers one argument containing spaces. The retained Wsh fixture supplies the missing byte, process-group, signal, suspension, reaping, and terminal assertions.

## Foreground and ordinary startup passed their fixed latency gates

Each foreground variant ran 5 warmups followed by 20 forward-order and 20 reverse-order retained launches. Timing began before PTY creation, recorded probe readiness, and ended at the first OSC 133 editable-prompt marker after probe exit.

| Path | PTY to probe ready median, ms | PTY to probe ready p90, ms | Probe ready to prompt median, ms | Probe ready to prompt p90, ms |
|---|---:|---:|---:|---:|
| Current reconstructed wrapper | 11.624 | 17.534 | 513.375 | 514.209 |
| Positional wrapper | 10.984 | 13.209 | 513.270 | 514.301 |
| `wsh run-foreground` | 10.468 | 11.675 | 0.787 | 0.851 |

The candidate's readiness p90 was 1.534 ms below the positional wrapper and passed the fixed maximum regression of +1 ms. Its prompt-return p90 was 513.358 ms below the current wrapper. The large wrapper return cost belongs to this complete edge-Zsh fixture, where the replacement shell initializes through the user startup directory and waits for unanswered terminal queries. Other shells and terminals can produce a different absolute cost, but the wrapper always performs the second shell initialization that the accepted path removes.

The dormant adapter was measured separately by interleaving baseline and candidate managed launches one at a time against their corresponding complete bundles. Each build retained 40 observations after 5 interleaved warmups, and blocking PTY reads ended at the same OSC 133 editable-prompt marker.

| Build | Managed first-editable median, ms | Managed first-editable p90, ms | Maximum, ms |
|---|---:|---:|---:|
| Baseline | 28.638 | 29.872 | 30.844 |
| Candidate | 28.634 | 30.297 | 31.611 |

Managed first-editable p90 increased by 0.425 ms and passed the fixed maximum regression of +0.5 ms.

The canonical builder then rebuilt the complete product and ran the Rust, runtime PTY, configuration, editing-default, doctor, foreground-startup, relocation, and imported-symbol gates inside the glibc 2.28 environment. Development bundle `238f745b915a1d829821b440a59d49d827bf4a1a1223ceb9a7e7d788c0f5af30` passed with `GLIBC_2.28` as its newest imported symbol.

## Process tracing confirms one owning Zsh

`strace -ff -e trace=process` observed two successful Zsh executions for the current wrapper and one for the candidate. The candidate otherwise executed the manager, the existing per-session runtime, one Git scan, and the requested probe. It added no supervisor or resident foreground-process service.

| Path | Successful executable count |
|---|---|
| Current wrapper | 2 Zsh, 1 runtime, 1 probe |
| `wsh run-foreground` | 1 manager, 1 Zsh, 1 runtime, 1 Git, 1 probe |

## Three rejected comparisons corrected the measured boundary

The first candidate timing supplied `--bundle`, which deliberately verifies every bundle file before launch. Candidate readiness p90 was 41.418 ms, roughly 30 ms above both wrappers. This did not represent an installed session, where Wsh reads the compact activation state.

The next timing polled the PTY at roughly 10 ms intervals while enforcing a 1 ms regression gate. Its quantized p90 values could not support that threshold. Replacing polling with blocking reads at the exact probe and prompt markers exposed a second mismatch: the wrappers loaded raw bundled Zsh while the candidate loaded the complete Wsh product. In that unmatched comparison, candidate readiness p90 was 11.875 ms versus 8.368 ms for the positional wrapper. The accepted comparison loads the same bundle integration and isolated user configuration before every application.

The first ordinary-startup comparison ran complete baseline and candidate batches separately. Repetition under changing host load swung managed p90 from 57.762 ms for one baseline batch to 29.075 ms for the later candidate batch. Per-launch interleaving and blocking prompt reads replaced that invalid design. All rejected raw inputs and summaries are retained, along with the unmatched process trace.

## Reproduction

```sh
./tests/foreground-startup.zsh <baseline-manager> <baseline-bundle> baseline
./tests/foreground-startup.zsh <candidate-manager> <candidate-bundle> candidate
WSH_FOREGROUND_CPU=0 ./benchmarks/benchmark-foreground-startup.zsh <output.tsv> <candidate-manager> <candidate-bundle> tests/fixtures/foreground-probe.c
./benchmarks/summarize-foreground-startup.zsh <output.tsv> <summary.tsv>
WSH_FIRST_EDITABLE_CPU=0 ./benchmarks/benchmark-managed-builds.zsh <output.tsv> <baseline-manager> <baseline-bundle> <candidate-manager> <candidate-bundle>
./benchmarks/summarize-managed-builds.zsh <output.tsv> <summary.tsv>
./benchmarks/trace-foreground-startup.zsh <new-output-directory> <candidate-manager> <candidate-bundle> tests/fixtures/foreground-probe.c
```

The exact revisions, binary and input hashes, commands, sample rules, gates, and host identity are recorded in [`metadata.txt`](metadata.txt). `./benchmarks/verify-foreground-startup-evidence.zsh` checks the retained hashes, regenerates both summaries, validates sample counts and thresholds, and verifies the process trace manifest.
