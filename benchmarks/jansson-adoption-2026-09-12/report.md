# System Jansson adoption passes host, floor and source-RPM checks

Wsh now uses system Jansson for the helper, profile reader and renderer test driver. The vendored yyjson source and license are removed. The selected helper passed the full host installed suite, sanitizer checks, glibc 2.28 qualification and offline Fedora source-RPM rebuild.

The final helper also passed the original paired latency gates after the Git-counter bound was added: the largest paired p95 increase was 0.778 ms for first-editable startup and 0.571 ms for Git refresh, below the fixed 3 ms limit. Both comparison installations used the same native shell bytes, with only the helper replaced. Its host executable remains 114,912 bytes. The [original comparison](https://github.com/wakamex/wsh/blob/ee6e97c/benchmarks/jansson-2026-09-12/report.md) retains memory measurements, protocol differences and the predeclared plan.

## Selected behavior

IDs, generations, durations and counters use the nonnegative INT64 range; JSON `-0` is zero. Out-of-range request values are rejected before state changes. Oversized Git ahead/behind counters take the existing invalid-counter fallback of zero, keeping the helper alive instead of reaching an unrepresentable JSON output value. Theme thresholds remain governed by the existing TOML parser.

The current installed suite includes 95 direct protocol boundary cases plus real-Git output faults, maximum signed counters, overflow, liveness and timeout tests. The same suites and the 15-case lifecycle suite pass with ASan/UBSan. Complete snapshots also match the reference helper across the real Git-state matrix, and the converted renderer driver matches all 400 archived prompt outputs.

## Distribution qualification

- Host upstream Zsh suite: 75 successful scripts, zero failures, two skips.
- Full host installed suite: passed, including real Oh My Zsh coexistence, native editor features, profiling, recovery, protocol and Git-output checks.
- Canonical glibc 2.28 build: reference and native upstream suites passed, the complete installed suite passed, and the generated RPM passed inventory/agreement tests.
- Fedora source RPM: source integrity and offline rebuild passed, including reference/native upstream suites, complete installed checks, normal RPM processing and debug-package generation.

The Fedora container previously failed to write `/builddir/packages.txt` when its builder account and the mounted directory owner differed. Mapping the host identity to container UID/GID 1000 reproduces and fixes that mismatch without changing host directory ownership. The namespace counterfactual and complete successful rebuild are retained.

## Evidence and reproduction

[Identity and commands](identity.json) record exact source inputs, package/helper hashes, manifests and commands. [Raw evidence](evidence.tar.gz) contains logs, test results, namespace observations and paired samples. [Latency summaries](summary.json) preserve unrounded measurements. These are unsigned development artifacts.

Use `build/build-native-installation.zsh` and `build/check-native-installation.zsh` for host validation, `build/build-glibc-2.28-development-bundle.zsh` for the canonical floor, and `packaging/test-source-rpm.zsh NEW_OUTPUT` for the offline rebuild. The retained floor command uses a fresh output directory because the default local cache belonged to another source lock. Host tests used separate temporary storage because the host `/tmp` was full and disabled host startup files that otherwise reintroduced an unrelated exported FPATH.

Paired Git-refresh and startup comparisons use the current `native/measure-git.py` and `native/measure-startup.py` harnesses, 50 alternating pairs per workload, tracing off and CPU 0. Every compared Git snapshot matched.
