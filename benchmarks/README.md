# Benchmark history

The [historical experiments](https://github.com/wakamex/wsh/tree/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks) retain reports, raw measurements, fixtures, source snapshots and their original verifiers in Git. Current builds and CI use current source and regression tests; they do not need these historical files.

To reproduce the historical evidence checks from a checkout with full Git history:

```sh
python3 benchmarks/verify-historical.py
```

The checker extracts the pinned tree, then runs that tree's original complete suite, including its earlier source revisions. It requires Python 3 with PyYAML, a C compiler, Git, tar, Zsh, jq and GNU awk. It verifies retained measurements and identities without rerunning timing experiments.

Run `./tests/verify-current.zsh` and the relevant installed tests for current changes. [Development](../DEVELOPMENT.md) describes current component measurement commands. Preserve new experiment inputs, raw results, commands and summaries in a Git commit, and link accepted claims to that immutable revision. Keep reusable test helpers with the current tests.

The [Jansson comparison](https://github.com/wakamex/wsh/blob/ee6e97c/benchmarks/jansson-2026-09-12/report.md), including its prototype, reproducer and raw evidence, is retained at `ee6e97c`. Run its verification and reproduction commands from that revision; current builds use system Jansson.
