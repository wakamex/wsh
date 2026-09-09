# Installation completion dump passes normal startup; fallback remains over budget

A read-only installation dump enables native completion at 39.645 ms startup p95 and 72.066 ms first-Tab p95. Registration and editor correctness pass, but stale or unusable dump fallback adds about 113 ms to startup against the fixed 100 ms limit. A bounded-read wrapper reduces read syscalls but makes fallback slower. Both interventions remain prototypes; automatic completion initialization remains unadopted.

| First matrix configuration | Shells | Startup p95 | Added startup p95 | First Tab p95 | Second Tab p95 | Fixed gate result |
|---|---:|---:|---:|---:|---:|---|
| No initialization | 50 | 25.081 ms | Baseline | Unavailable | Unavailable | Reproduces standalone gap |
| Ordinary compinit, missing user dump | 50 | 153.644 ms | 128.563 ms | 71.710 ms | 25.314 ms | Exceeds +100 ms startup |
| Ordinary compinit, reusable user dump | 50 | 38.398 ms | 13.317 ms | 71.650 ms | 25.085 ms | Passes +20 ms startup and 100 ms Tab gates |
| Valid installation dump | 50 | 39.645 ms | 14.564 ms | 72.066 ms | 25.033 ms | Passes +20 ms startup and 100 ms Tab gates |
| Stale installation dump | 50 | 138.475 ms | 113.395 ms | 72.981 ms | 25.350 ms | Exceeds +100 ms fallback startup |
| Unusable installation dump | 50 | 138.349 ms | 113.268 ms | 74.706 ms | 25.558 ms | Exceeds +100 ms fallback startup |

## Registration scanning dominates cold initialization

Fifty alternating plain/timed pairs in each cache state split actual native compinit into audit, registration scanning and dump generation. Cold medians are 11.684 ms audit, 109.797 ms scanning and 26.463 ms dump generation, within 149.355 ms total. Warm initialization is 17.380 ms overall and avoids scanning and generation. Buffered-clock overhead passes the predeclared paired p95 threshold at 2.971 ms cold and 0.404 ms warm. Event formatting and output happen after the operation.

That diagnostic's retained effective fpath includes both the relocated installation and the original development build directory. Both final ZLE matrices explicitly select the installed bundled function directory through FPATH. This holds the workload constant and avoids using a build-tree duplicate to define system-package behavior. Custom and shadowing fpath entries are tested independently. Final package qualification still needs its actual installed resource paths.

## Read-only dump behavior and correctness

The private compinit copy adds -R: it loads a valid dump but never writes or regenerates that selected file. Native compaudit and count/version invalidation remain enabled; an invalid dump falls back to the existing registration scan. Existing -D and ordinary initialization keep their behavior. After initialization, the prototype restores the ordinary per-user _comp_dumpfile, so later explicit compdump does not target the installation seed. No cache database, background initializer or audit bypass is introduced.

Nine comparisons against actual upstream compinit preserve registrations for valid, missing, stale-count, stale-version, directory, unreadable, custom, shadowing and insecure-directory inputs. The candidate dump stays unchanged or absent. Ten actual-ZLE cases cover controls, valid/stale/unusable seed, vi insert mode, z as first completion, custom Tab and existing compinit. They verify Git branches, spaced paths, directory jumping, custom widgets, history search, autosuggestion display/acceptance and highlighting. Existing completion and custom Tab ownership remain intact.

Ordinary compinit generates the seed from bundled functions only. It is executable initialization data with the same installation authority as those functions; it does not change theme authority. The prototype stays outside normal Wsh startup and the source lock.

## Bounded-read wrapper fails the performance comparison

The old no-dump diagnostic performs 25,552 read calls. The wrapper uses the existing zsh/system sysread builtin to read at most 4 KiB, parses a complete first line with native parameter expansion, and falls back to ordinary read for incomplete/long headers or an unavailable module. Reads fall to 1,327, but per-file descriptor handling and interpreted commands increase. Opens rise from 2,071 to 4,021 and closes from 4,048 to 8,922.

| Second matrix configuration | Startup p95 | Added startup p95 | First Tab p95 | Gate result |
|---|---:|---:|---:|---|
| Valid installation dump | 39.548 ms | 14.381 ms | 71.687 ms | Passes |
| Stale dump with bounded-read wrapper | 178.492 ms | 153.325 ms | 72.054 ms | Fails fallback startup |
| Unusable dump with bounded-read wrapper | 180.605 ms | 155.438 ms | 72.156 ms | Fails fallback startup |

The wrapper first failed exact header parity because read preserves a trailing empty field. The corrected version passes 2,017 cases with whitespace, quoting, NUL, malformed encodings and the 4 KiB boundary. It repeats registration and ZLE checks before timing and preserves registrations when zsh/system is unavailable. The failed header comparison and both timing matrices remain retained.

## Premise audit and retained decision

Fewer syscalls did not lower initialization latency when achieving that reduction added interpreted per-file work. Reject the wrapper. The read-only installation dump helps its valid path, but this experiment does not waive the fallback startup gate or enable it for everyone.

A native input or registration optimization needs a new bounded experiment. Buffering general read must preserve shared file offsets, signals, traps, delimiters and nonseekable input; replacing compdef registration must preserve configuration semantics. Neither is admitted merely to erase the remaining 13 ms fallback overrun. User/framework-owned compinit remains available, and the seed prototype can support a deliberate continuation. This completes the bounded stage-8 experiments with an unresolved admission decision.

## Reproduction and retained evidence

Each final matrix retains 50 alternating repetitions of six configurations, 300 shells per matrix. Startup observes native OSC 133 editor readiness; the existing actual-ZLE capture observer records both Tabs. Timing stages run sequentially on CPU 0 without concurrent builds or tests. Added startup is the difference between marginal p95 values, matching the established completion gate. No sample is excluded.

Run native/prepare-completion-prototype.py with BUNDLE and OUTPUT for the read-only seed, adding --bulk for the rejected wrapper. Native registration/file checks are in native/test-completion-dump.py; header comparison is in native/test-completion-headers.py. Run native/test-completion-seed.py with BUNDLE, PROTOTYPE, OUTPUT and correctness, then measure. Native/measure-compinit.py reproduces the buffered diagnostic. Source, generated functions/dumps, configurations, samples, transcripts, syscall reports and identities are retained and checked through the shared evidence entrypoint.
