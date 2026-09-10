# Recognized directory-jump takeover

The user's standard OMZ `z` copy now uses native queries and persistence in Wsh. Takeover preserves its initialized aliases, database, settings, completion bindings and hook order. Host and glibc 2.28 tests pass, including removal state carried from `.zshrc`, modified implementations, custom command names, unload and real Tab completion. Startup adds at most 1.780 ms at paired p95, passing the 3 ms gate over 50 alternating pairs per prompt mode.

| Prompt mode with exact upstream z loaded in startup | Baseline median readiness | Native takeover median readiness | Paired p95 added readiness | Gate |
|---|---:|---:|---:|---|
| Existing prompt | 16.604 ms | 18.094 ms | 1.780 ms | <= 3 ms, pass |
| Wsh minimal prompt | 17.543 ms | 18.961 ms | 1.776 ms | <= 3 ms, pass |

## Baseline and gate

Baseline `9a5c703` preserves every existing directory-jump implementation. The user's unmodified OMZ `z` runtime is byte-identical to Wsh's pinned source, but therefore still executes the interpreted query/persistence engine. The smallest intervention replaces `zshz`, recording/chpwd functions and unload cleanup from the generated native adapter while retaining existing lifecycle registration, aliases, fpath ownership, completion configuration and settings.

Before testing, require native ownership for the recognized source, preserved modified source/functions/aliases and explicit disable behavior, unchanged database path and existing entries, ranking and custom-command/settings parity, working real Tab completion, one recording hook per event and preserved remove-until-chpwd state. Matched startup paired p95 overhead must remain <= 3 ms over 50 pairs per prompt mode. Test correctness before timing; two failed interventions at a gate require a new hypothesis.

## Recognition and lifecycle

Ownership follows the selected command's standard `zshz 2>&1` alias, exact pinned runtime bytes, and persistent entrypoint/lifecycle function provenance. OMZ's `_z` completion function is allowed to coexist. Query-local helpers are redefined on every upstream invocation and Zsh attributes them to the invoking startup file; they are not stable implementation-ownership signals. Modified entrypoints, persistent helpers, hooks and command aliases remain external.

The generated takeover file defines only native query/persistence, recording/chpwd and unload functions. It does not reinitialize widget bindings, fpath bookkeeping, aliases, completion registrations or settings. An inherited `ZSHZ[DIRECTORY_REMOVED]` continues to suppress recording until `chpwd`, which clears both the inherited flag and native removal state. Native remove suppression and unload cleanup remain active afterward.

## Verification and reproduction

All nine host installation suites pass, including the real user's OMZ checkout. The directory regression covers 13 host ownership/configuration cases and 12 cases on glibc 2.28, then verifies database persistence across sessions, completion with spaces and automatic visit recording through real ZLE. The initialized database is unchanged at takeover. The query/persistence comparison preserves nine byte-identical cases and the previously qualified tab-path encoding difference; C implementation and its prior sanitizer qualification are unchanged. The host upstream Zsh suite passes 75 scripts with zero failures and two skips.

The actual personal `.zshrc` reports `WSH_DIRECTORY_JUMP_OWNER=wsh` and `WSH_DIRECTORY_JUMP_REPLACED=1`. Regular Zsh retains external ownership. Existing highlighting regions, completion and Ctrl-C checks pass, and `.zshrc`/`.zshenv` hashes remain unchanged. Private traces are retained under `/var/tmp/wsh-directory-takeover/user`.

Run `zsh tests/directory-jump.zsh INSTALLATION [OMZ_CHECKOUT]`, `python3 native/check-installation.py INSTALLATION OUTPUT` and `python3 native/measure-directory-takeover.py BASELINE_INSTALLATION CANDIDATE_INSTALLATION OUTPUT`. Timing uses the same upstream plugin, CPU 0, tracing off and native OSC 133 B readiness. The preserved input fixture and raw samples are in `evidence.tar.gz`; source, compiler, target, build command and executable identities are in `identity.json`.

The glibc 2.28 component fixture reuses the previously qualified native executable with current integration and generated directory adapters overlaid, then refreshes and verifies its inventory. This scoped run does not rebuild or requalify an RPM. All artifacts are unsigned development artifacts.
