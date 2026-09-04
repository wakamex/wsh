# Native Zsh can own Wsh terminal integration

Wsh can use native Zsh for OSC 7 working-directory reports and OSC 133 prompt and command zones without a broad Zsh fork or a second shell-lifecycle implementation. Two defects in the selected post-5.9 Zsh revision required six changed source lines in one digest-pinned patch: every generated prompt identifier was malformed for Wakterm, and disabling an optional 500 ms terminal query also suppressed the initial directory report and directory restoration after child output. The patched producer passed Wakterm's real parser, the complete upstream Zsh suite, the Wsh PTY suite, and the glibc 2.28 floor.

Wakterm now skips only its duplicate OSC 7 and OSC 133 paths when Wsh owns them. The accepted coexistence path started zero `wakterm set-working-directory` processes and completed 100 no-op prompt cycles at 60.500 ms p90, compared with 60.552 ms for native-only. Leaving both reporters enabled took 499.381 ms p90 and produced duplicate lifecycle regions. The comparison used one fixed CPU, 5 warmups, and 40 retained interleaved runs per path.

## Two native producer defects caused the failures

The prompt template contained `aid=zZZZZZZ`, but upstream copied its generated identifier at fixed offset 13. That overwrote the field name instead of the six `Z` placeholder bytes. Wakterm's authoritative parser therefore accepted 0 of 10 native prompt-start markers.

Upstream emitted its initial OSC 7 report as a side effect of the terminal-query function. The earlier edge-Zsh experiment disabled that query because a PTY that did not answer waited 500 ms. This also removed the initial directory report. Zsh otherwise emitted OSC 7 only after `chpwd`, so a foreground child could publish a remote cwd and leave the terminal with that stale value after returning to the unchanged shell directory.

The patch copies the identifier into the named placeholder and emits the current directory from the native prompt-read path. Reporting before every editable prompt establishes the shell's context after any foreground application may have changed it. A Zsh wrapper or Wsh hook could only mask both native defects by installing another prompt lifecycle owner.

## Correctness passed with one native lifecycle

The isolated PTY workload created user `precmd` and `preexec` hooks, then exercised empty input, `:`, `false`, `cd`, a child-emitted remote OSC 7 value, multiline input, output without a trailing newline, and Ctrl-C while editing. It captured raw bytes and counted exact markers.

| Path | Prompt starts | Wakterm-valid starts | Prompt ends | Command starts | Command ends | Local cwd reports | Child cwd reset | User `precmd` | User `preexec` |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| Unpatched native | 10 | 0 | 10 | 7 | 6 | 1 | No | 9 | 7 |
| Unpatched native plus Wakterm reporters | 19 | 0 | 20 | 14 | 14 | 10 | Yes | 9 | 7 |
| Unpatched native with Wakterm duplicate reporters skipped | 10 | 0 | 10 | 7 | 6 | 1 | No | 9 | 7 |
| Patched native | 10 | 10 | 10 | 7 | 6 | 10 | Yes | 9 | 7 |
| Patched native with Wakterm duplicate reporters skipped | 10 | 10 | 10 | 7 | 6 | 10 | Yes | 9 | 7 |

Empty input produced another native prompt without a command region. Wakterm's duplicate path instead added a false command end and another prompt lifecycle. The accepted path preserved the existing hook counts and restored the local cwd after the child-emitted remote value.

Wakterm's `FinalTermSemanticPrompt` parser passed an exact native prompt marker with `cl=m` followed by `aid=zAbC123`. This regression uses the same parser that consumes terminal input rather than a Wsh approximation.

## Duplicate integration added processes and latency

Process tracing used `strace -ff -qq -e trace=process` around the same correctness workload after the native patch.

| Path | `wakterm set-working-directory` executions |
|---|---:|
| Native | 0 |
| Native plus Wakterm reporters | 9 |
| Accepted coexistence | 0 |

The prompt-cycle benchmark ran 100 `:` commands per sample with blocking PTY reads ending at complete OSC 133 `B` markers. Runs alternated forward and reverse path order on CPU 31.

| Path | Retained runs | p50 ms | p90 ms | Minimum ms | Maximum ms |
|---|---:|---:|---:|---:|---:|
| Native | 40 | 54.492 | 60.552 | 39.963 | 62.074 |
| Duplicate Wakterm reporters | 40 | 486.714 | 499.381 | 474.662 | 509.698 |
| Accepted coexistence | 40 | 52.871 | 60.500 | 41.103 | 64.635 |

Accepted coexistence was 0.052 ms lower than native at p90 and passed the fixed maximum regression of +0.5 ms. The large duplicate cost includes Wakterm's command invocation and duplicated shell integration under this exact workload.

## Exact first-job startup remains thin Wsh glue

Native Zsh reports commands entered through its editor, but `wsh -- <command> [arguments...]` runs one exact argument vector before the first editable command. The earlier adapter executed that array correctly but emitted no OSC 133 command boundaries. The accepted one-shot callback follows `.term.extensions`, emits `C` immediately before the array and `D` after it returns, and then lets native Zsh emit OSC 7 and the first `A` and `B` prompt markers.

The existing foreground fixture still passes empty, whitespace, quoted, newline, dollar, glob, Unicode, and non-UTF-8 arguments; normal and consumed Ctrl-C; Ctrl-Z and `fg` with the same PID and process group; nested children; terminal-mode restoration; login and non-login startup; and 20 repeated launches. `wsh --` and `wsh run-foreground ... --` both use this path. Disabling native integration through `.term.extensions=(-query -integration)` suppresses both the first-job markers and the later native sequences.

Normal Zsh command strings remain available through `wsh run -- -c '<source>'`. The exact first-job interface is an argument vector because Wakterm already has an executable and arguments and must not reconstruct them as shell source. Zsh's `-e` retains its existing `ERR_EXIT` meaning.

## Wakterm does not need another job-transition protocol

The separate managed-frontend reproducer now passes with Wakterm's owner-local fix. It records the verified frontend PID and process start time through the existing 300 ms process-snapshot cache, preserves the binding while the process is stopped, and clears it when that frontend exits or is replaced. Targeted tests pass managed start, exit after Ctrl-C, consumed Ctrl-C, Ctrl-Z, `fg`, replacement by an ordinary TUI, and PID identity checks.

That fix adds no watcher, child process, prompt hook, or independent polling loop. A new shell protocol for `started`, `stopped`, `continued`, and `finished` transitions would duplicate a passing owner and is deferred until a reproduced transition error or measurable polling cost establishes a benefit.

## The distribution carries a narrow upstreamable patch

The result supports a patched Zsh distribution rather than a divergent shell fork. Zsh continues to own language parsing, `-c`, `-e`, job control, ZLE, and ordinary OSC reporting. Wsh owns exact first-job startup, source selection, the digest-pinned patch queue, complete-bundle validation, and the measured integration policy. A terminal can call Wsh with an argument vector and consume standard OSC sequences without becoming shell-aware.

The source-patched revision passed all 75 upstream test scripts with 0 failures and 2 existing environment-dependent skips. The complete Wsh suite then passed with PTY harnesses driven by the exact bundled Zsh. This harness selection matters because Rocky Linux 8.10's system Zsh 5.5 timed out in the autosuggestion cancellation fixture while the exact same fixture repeatedly passed under the bundled Zsh on both Fedora and Rocky.

The canonical floor build produced development bundle `3d90af09e92fad04aa7b19b42f8bed412f902282c1c2c2ed335e69db93b59351` and archive SHA-256 `7b19bf8a2f9d3f45f4bde5a3a492b8d69e8e40d4057a81323eef052f5276b0ab`. Every included ELF stayed at or below `GLIBC_2.28`. The bundle manifest records source patch SHA-256 `b4c048789cac67a0b07d4d2644a8de266dafa279ac570a6419e5080403dfc5f8`.

## Reproduction

```sh
WAKTERM_INTEGRATION=${WAKTERM_INTEGRATION:?set this to Wakterm's assets/shell-integration/wakterm.sh}
./build/build-zsh.zsh
WSH_EXPECT_NATIVE_TERMINAL_PASS=1 ./tests/native-terminal-integration.zsh build/out/zsh-cad0d67c-wsh1/bin/zsh "$WAKTERM_INTEGRATION" native /tmp/native.bin
WSH_EXPECT_NATIVE_TERMINAL_PASS=1 ./tests/native-terminal-integration.zsh build/out/zsh-cad0d67c-wsh1/bin/zsh "$WAKTERM_INTEGRATION" coexist /tmp/coexist.bin
taskset -c 31 ./benchmarks/benchmark-native-terminal-integration.zsh build/out/zsh-cad0d67c-wsh1/bin/zsh "$WAKTERM_INTEGRATION" /tmp/prompt-cycle.tsv
./benchmarks/summarize-native-terminal-integration.zsh /tmp/prompt-cycle.tsv /tmp/prompt-cycle-summary.tsv
./benchmarks/trace-native-terminal-integration.zsh build/out/zsh-cad0d67c-wsh1/bin/zsh "$WAKTERM_INTEGRATION" /tmp/process-trace
./tests/foreground-startup.zsh target/release/wsh <bundle> candidate
./build/build-glibc-2.28-development-bundle.zsh
```

The retained experiment covers one x86-64 host, Wakterm's current Zsh integration and parser, the selected Zsh revision, and the listed PTY transitions. Other terminals can consume the standard sequences, but terminal-specific rendering and nesting behavior require their own concrete reproducers.
