# Oh My Zsh z plugin at d745fbf

Wsh 0.4.4 recognizes the `z` plugin bundled with Oh My Zsh at upstream commit [`d745fbf`](https://github.com/ohmyzsh/ohmyzsh/commit/d745fbf3bd49a5038e089d7d343ca89db0cbaaff) and hands its directory jumping to the native implementation. The entry passes the real-startup handoff matrix, and startup with all five recognized plugins adds at most 0.70 ms at the paired 95th percentile, within the 3 ms gate.

## Upstream change

The daily upstream check reported the file as changed. Oh My Zsh updated its bundled [zsh-z](https://github.com/agkozak/zsh-z) to create its data and lock files with forced append (`>>|`), which works under `NO_CLOBBER` with `APPEND_CREATE` unset, and to unset its file-descriptor variable before allocating one. Function names, settings and options are unchanged, so the existing `preserve-directory-lifecycle` handoff applies. Wsh's native directory implementation creates its files with `open()`; a real login session with `NO_CLOBBER` set and `APPEND_CREATE` unset created both files and jumped correctly.

The file at `d745fbf` is byte-identical to the file at upstream `master` `60c9a7a` checked by the monitor, and `d745fbf` is the last commit to change it. The snapshot is retained unchanged under `third_party/plugin-catalog/snapshots/` with its embedded license notice.

## Results

| Check | Result |
| --- | --- |
| Catalog checks | 19 snapshots and fingerprints verified; input bounds and upstream mapping checks pass |
| Live upstream check | All six configured mappings are known after the entry |
| Handoff matrix | 83 cases pass, including exact handoff, modified-copy rejection and function-override preservation for the new entry, through both the catalog and the local Git check |
| Installed suite | The complete installed suite passes on the 0.4.4 development installation |

| Startup workload, all five recognized plugins | 0.4.3 median readiness | 0.4.4 median readiness | Paired p95 added readiness | Gate |
| --- | ---: | ---: | ---: | --- |
| Existing prompt | 56.61 ms | 56.11 ms | 0.70 ms | <= 3 ms, pass |
| Wsh minimal prompt | 33.95 ms | 33.75 ms | 0.42 ms | <= 3 ms, pass |

Each workload uses 50 alternating pairs. The startup fixture loads the previously cataloged `z` file, so it measures the cost of the larger catalog table on every startup.

[Identity](identity.json) records the installations, sources and upstream revision; [evidence](evidence.tar.gz) retains the raw samples, summaries, matrix results, upstream check results and suite log, covered by `SHA256SUMS`. The glibc 2.28 floor suite runs in the release-eligibility check for the release commit.
